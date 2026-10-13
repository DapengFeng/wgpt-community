"""Synthetic CLA evidence and GitHub transport tests; no real signatures or API calls."""

import base64
import copy
import hashlib
import json
import runpy
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import urllib.response
from dataclasses import replace
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cla.gate import SignatureGate, contributor_ids
from cla.github import GitHubClient, GitHubError, _NoRedirect
from cla.policy import load_policy
from cla.signatures import (
    LedgerSnapshot,
    apply_comment_event,
    latest_signatures,
    read_ledger,
    record_comment,
    revoke,
    validate_record,
    verify_live_signature,
    write_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = load_policy(ROOT)
PREFIX = "/repos/" + POLICY.repository
STAMP = "2026-01-02T03:04:05Z"
SHA = "a" * 40


def user(identifier=101, login="fixture-contributor", kind="User"):
    return {"id": identifier, "login": login, "type": kind}


def pull(number=7, author=None, head=SHA):
    return {
        "number": number, "user": author or user(), "state": "open", "commits": 1,
        "head": {"sha": head}, "base": {"ref": "main", "repo": {"id": POLICY.source_repository_id}},
    }


def comment(identifier=201, number=7, author=None):
    return {
        "id": identifier, "user": author or user(), "body": POLICY.statement,
        "created_at": STAMP, "updated_at": STAMP,
        "issue_url": f"https://api.github.com/repos/{POLICY.repository}/issues/{number}",
    }


def record():
    return record_comment(comment(), pull(), POLICY)


def contents(records, sha="b" * 40):
    data = {"schema_version": 1, "signatures": records}
    return {"type": "file", "encoding": "base64", "sha": sha, "content": base64.b64encode(json.dumps(data).encode()).decode()}


class FakeGitHub:
    def __init__(self, records=None):
        self.calls = []
        self.responses = {
            ("GET", PREFIX): {"id": POLICY.source_repository_id, "full_name": POLICY.repository, "private": False},
            ("GET", PREFIX + "/pulls/7"): pull(),
            ("GET", PREFIX + "/issues/comments/201"): comment(),
            ("GET", PREFIX + "/contents/" + POLICY.signatures_path + "?ref=cla-signatures"): contents(records or []),
        }
        self.lists = {
            PREFIX + "/pulls?state=open&base=main": [pull()],
            PREFIX + "/pulls/7/commits": [{"sha": SHA, "author": user(), "commit": {"message": "Synthetic fixture"}}],
            PREFIX + "/issues/7/comments": [],
        }

    def request(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if (method, path) in self.responses:
            value = self.responses[(method, path)]
            if isinstance(value, Exception):
                raise value
            if callable(value):
                return value()
            return copy.deepcopy(value)
        if method == "GET":
            raise AssertionError("Unexpected fixture request: " + path)
        if method == "PUT" and "/contents/" in path:
            data = base64.b64decode(body["content"])
            digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False).hexdigest()
            return {"content": {"sha": digest, "path": path.split("/contents/", 1)[1]}}
        return {}

    def paginate(self, path, max_pages=10):
        self.calls.append(("PAGINATE", path, None))
        value = self.lists[path]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def statuses(self):
        return [(path.rsplit("/", 1)[-1], body["state"]) for method, path, body in self.calls if method == "POST" and "/statuses/" in path]


class SignatureTests(unittest.TestCase):
    def test_document_hash_is_required_and_statement_has_no_account_name(self):
        self.assertNotIn(user()["login"], POLICY.statement)
        self.assertIn(POLICY.document_sha256, POLICY.statement)
        self.assertTrue(POLICY.statement.endswith("Please invite me to collaborate on DapengFeng/wgpt."))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "cla").mkdir()
            (root / "cla/policy.json").write_bytes((ROOT / "cla/policy.json").read_bytes())
            (root / "CLA.md").write_text("Modified agreement", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest"):
                load_policy(root)

    def test_signature_requires_exact_body_and_pr_author(self):
        self.assertIsNotNone(record())
        for mutation in (
            {"body": " " + POLICY.statement}, {"body": POLICY.statement + "\n"},
            {"body": "```\n" + POLICY.statement + "\n```"},
            {"user": user(102, "other-person")},
            {"user": user(103, "fixture-bot", "Bot")},
            {"updated_at": "2026-01-02T03:04:06Z"},
            {"issue_url": "https://api.github.com/repos/other/repository/issues/7"},
        ):
            with self.subTest(mutation=mutation):
                value = comment()
                value.update(mutation)
                self.assertIsNone(record_comment(value, pull(), POLICY))

    def test_live_identity_survives_login_change_but_not_account_replacement(self):
        client = FakeGitHub()
        value = client.responses[("GET", PREFIX + "/issues/comments/201")]
        value["user"]["login"] = "renamed-fixture"
        self.assertTrue(verify_live_signature(client, POLICY, record()))
        value["user"]["id"] = 999
        self.assertFalse(verify_live_signature(client, POLICY, record()))

    def test_live_changed_or_missing_comment_is_invalid_but_api_failure_raises(self):
        for value in (
            dict(comment(), body="Withdrawn"),
            dict(comment(), updated_at="2026-01-02T03:04:06Z"),
            GitHubError(404),
        ):
            client = FakeGitHub()
            client.responses[("GET", PREFIX + "/issues/comments/201")] = value
            self.assertFalse(verify_live_signature(client, POLICY, record()))
        for status in (403, 429, 500):
            client.responses[("GET", PREFIX + "/issues/comments/201")] = GitHubError(status)
            with self.assertRaises(GitHubError):
                verify_live_signature(client, POLICY, record())

    def test_old_version_or_document_does_not_sign_current_agreement(self):
        for policy in (replace(POLICY, cla_version="2"), replace(POLICY, document_sha256="f" * 64)):
            client = FakeGitHub()
            self.assertFalse(verify_live_signature(client, policy, record()))
            self.assertEqual(client.calls, [])

    def test_ledger_round_trip_preserves_cas_and_separate_branch(self):
        client = FakeGitHub([record()])
        snapshot = read_ledger(client, POLICY)
        self.assertEqual(snapshot.records, [record()])
        write_ledger(client, POLICY, snapshot)
        method, path, body = client.calls[-1]
        self.assertEqual((method, path), ("PUT", PREFIX + "/contents/" + POLICY.signatures_path))
        self.assertEqual(body["sha"], "b" * 40)
        self.assertEqual(body["branch"], "cla-signatures")
        self.assertEqual(json.loads(base64.b64decode(body["content"]))["signatures"], [record()])

    def test_unconfirmed_ledger_write_is_not_accepted(self):
        for result in ({}, {"content": {"path": POLICY.signatures_path, "sha": "0" * 40}}):
            client = FakeGitHub()
            client.responses[("PUT", PREFIX + "/contents/" + POLICY.signatures_path)] = result
            with self.assertRaisesRegex(ValueError, "confirm"):
                write_ledger(client, POLICY, LedgerSnapshot([record()], "b" * 40))

    def test_missing_ledger_is_empty_but_authentication_errors_are_not(self):
        client = FakeGitHub()
        path = PREFIX + "/contents/" + POLICY.signatures_path + "?ref=cla-signatures"
        client.responses[("GET", path)] = GitHubError(404)
        self.assertEqual(read_ledger(client, POLICY), LedgerSnapshot([], None))
        client.responses[("GET", path)] = GitHubError(403)
        with self.assertRaises(GitHubError):
            read_ledger(client, POLICY)

    def test_malformed_and_duplicate_records_fail_closed(self):
        for field, value in (("user_id", True), ("status", "approved"), ("updated_at", "wrong"), ("login", "fixture[bot]")):
            invalid = record()
            invalid[field] = value
            with self.assertRaises(ValueError):
                validate_record(invalid)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_ledger(FakeGitHub([record(), record()]), POLICY)

    def test_comment_creation_records_once_without_trusting_payload_body(self):
        client = FakeGitHub()
        ledger = LedgerSnapshot([], "b" * 40)
        event = {"action": "created", "comment": {"id": 201, "body": "Untrusted payload"}, "issue": {"number": 7, "pull_request": {"url": "unused"}}}
        self.assertTrue(apply_comment_event(client, POLICY, ledger, event))
        self.assertEqual(ledger.records, [record()])
        self.assertFalse(apply_comment_event(client, POLICY, ledger, event))

    def test_edit_and_delete_revoke_without_erasing_history(self):
        for action in ("edited", "deleted"):
            ledger = LedgerSnapshot([record()], "b" * 40)
            event = {"action": action, "comment": {"id": 201}, "issue": {"number": 7, "pull_request": {"url": "unused"}}}
            self.assertTrue(apply_comment_event(FakeGitHub(), POLICY, ledger, event))
            self.assertEqual(len(ledger.records), 1)
            self.assertEqual(ledger.records[0]["status"], "revoked")
            self.assertFalse(apply_comment_event(FakeGitHub(), POLICY, ledger, event))

    def test_revocation_never_falls_back_to_older_active_signature(self):
        first = record()
        second = dict(first, comment_id=202)
        revoke(second, "comment_deleted", STAMP)
        self.assertEqual(latest_signatures([first, second], POLICY)[101], second)
        third = dict(first, comment_id=203)
        self.assertEqual(latest_signatures([first, second, third], POLICY)[101], third)


class GateTests(unittest.TestCase):
    def event(self):
        return {"repository": {"id": POLICY.source_repository_id}}

    def test_unsigned_pr_fails_with_exact_current_signing_instructions(self):
        client = FakeGitHub()
        result = SignatureGate(client, POLICY, document_revision="d" * 40).run("workflow_dispatch", self.event())
        self.assertEqual(result, {"checked_pull_requests": 1, "passed": 0})
        self.assertEqual(client.statuses(), [(SHA, "pending"), (SHA, "failure")])
        text = next(body["body"] for method, path, body in client.calls if method == "POST" and path.endswith("/comments"))
        self.assertIn(POLICY.statement, text)
        self.assertIn("/blob/" + "d" * 40 + "/CLA.md", text)
        for method, path, body in client.calls:
            if method == "POST" and "/statuses/" in path:
                self.assertIn("/blob/" + "d" * 40 + "/CLA.md", body["target_url"])

    def test_valid_old_signature_is_reused_for_same_user_on_new_pr(self):
        client = FakeGitHub([record()])
        client.lists[PREFIX + "/pulls?state=open&base=main"] = [pull(number=8)]
        client.responses[("GET", PREFIX + "/pulls/8")] = pull(number=8)
        client.lists[PREFIX + "/pulls/8/commits"] = copy.deepcopy(client.lists[PREFIX + "/pulls/7/commits"])
        client.lists[PREFIX + "/issues/8/comments"] = []
        SignatureGate(client, POLICY, document_revision="d" * 40).run("pull_request_target", self.event())
        self.assertEqual(client.statuses(), [(SHA, "pending"), (SHA, "success")])
        self.assertFalse(any(method == "PUT" for method, _, _ in client.calls))

    def test_other_commit_author_must_also_sign(self):
        client = FakeGitHub([record()])
        client.lists[PREFIX + "/pulls/7/commits"][0]["author"] = user(102, "another-contributor")
        SignatureGate(client, POLICY, document_revision="d" * 40).run("pull_request_target", self.event())
        self.assertEqual(client.statuses()[-1], (SHA, "failure"))

    def test_scheduled_reconciliation_recovers_a_missed_signing_event(self):
        client = FakeGitHub()
        client.lists[PREFIX + "/issues/7/comments"] = [comment()]
        result = SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertEqual(result["passed"], 1)
        self.assertEqual(client.statuses()[-1], (SHA, "success"))
        body = next(body for method, _, body in client.calls if method == "PUT")
        self.assertEqual(json.loads(base64.b64decode(body["content"]))["signatures"], [record()])
        self.assertEqual(sum(method == "PAGINATE" and path.endswith("/comments") for method, path, _ in client.calls), 1)

    def test_reconciliation_reads_signing_comments_beyond_the_first_page(self):
        path = PREFIX + "/issues/7/comments"
        class PaginatedGitHub(FakeGitHub):
            def paginate(self, value, max_pages=10):
                if value == path:
                    return GitHubClient.paginate(self, value, max_pages)
                return super().paginate(value, max_pages)
        client = PaginatedGitHub()
        client.responses[("GET", path + "?per_page=100&page=1")] = [dict(comment(identifier=300 + index), body="Unrelated discussion") for index in range(100)]
        client.responses[("GET", path + "?per_page=100&page=2")] = [comment()]
        SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertEqual(client.statuses()[-1], (SHA, "success"))
        body = next(body for method, _, body in client.calls if method == "PUT")
        self.assertEqual(json.loads(base64.b64decode(body["content"]))["signatures"], [record()])

    def test_reconciliation_never_revives_a_known_revoked_comment(self):
        revoked = record()
        revoke(revoked, "comment_edited", STAMP)
        client = FakeGitHub([revoked])
        client.lists[PREFIX + "/issues/7/comments"] = [comment()]
        SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertEqual(client.statuses()[-1], (SHA, "failure"))
        self.assertFalse(any(method == "PUT" for method, _, _ in client.calls))

    def test_edit_event_revokes_before_comment_reconciliation(self):
        client = FakeGitHub([record()])
        client.lists[PREFIX + "/issues/7/comments"] = [comment()]
        event = self.event() | {"action": "edited", "comment": {"id": 201}, "issue": {"number": 7, "pull_request": {"url": "unused"}}}
        SignatureGate(client, POLICY, document_revision="d" * 40).run("issue_comment", event)
        self.assertEqual(client.statuses()[-1], (SHA, "failure"))
        body = next(body for method, _, body in client.calls if method == "PUT")
        records = json.loads(base64.b64decode(body["content"]))["signatures"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "revoked")

    def test_reconciliation_does_not_sign_edited_or_outdated_unrecorded_comments(self):
        for value in (
            dict(comment(), updated_at="2026-01-02T03:04:06Z"),
            dict(comment(), body=replace(POLICY, cla_version="999").statement),
        ):
            client = FakeGitHub()
            client.lists[PREFIX + "/issues/7/comments"] = [value]
            SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
            self.assertEqual(client.statuses()[-1], (SHA, "failure"))
            self.assertFalse(any(method == "PUT" for method, _, _ in client.calls))

    def test_comment_pagination_failure_blocks_previously_signed_pr(self):
        for failure in (GitHubError(503), ValueError("GitHub pagination limit reached")):
            client = FakeGitHub([record()])
            client.lists[PREFIX + "/issues/7/comments"] = failure
            with self.assertRaises(type(failure)):
                SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
            self.assertEqual(client.statuses(), [(SHA, "pending"), (SHA, "error")])
            self.assertFalse(any(method == "PUT" for method, _, _ in client.calls))

    def test_unknown_author_coauthors_and_incomplete_history_fail_closed(self):
        for change in ({"author": None}, {"sha": "c" * 40}, {"commit": {"message": "Fixture\n\nCo-authored-by: Name <fixture@example.invalid>"}}):
            client = FakeGitHub([record()])
            client.lists[PREFIX + "/pulls/7/commits"][0].update(change)
            SignatureGate(client, POLICY, document_revision="d" * 40).run("pull_request_target", self.event())
            self.assertEqual(client.statuses()[-1], (SHA, "failure"))

    def test_bot_commit_is_excluded_but_bot_pr_author_cannot_sign(self):
        client = FakeGitHub()
        client.lists[PREFIX + "/pulls/7/commits"][0]["author"] = user(105, "fixture[bot]", "Bot")
        self.assertEqual(contributor_ids(client, POLICY, pull()), {101})
        with self.assertRaises(ValueError):
            contributor_ids(client, POLICY, pull(author=user(105, "fixture-bot", "Bot")))

    def test_live_edit_revokes_and_persists_before_publishing_failure(self):
        client = FakeGitHub([record()])
        client.responses[("GET", PREFIX + "/issues/comments/201")]["updated_at"] = "2026-01-02T03:04:06Z"
        SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        writes = [(index, body) for index, (method, _, body) in enumerate(client.calls) if method == "PUT"]
        self.assertEqual(len(writes), 1)
        data = json.loads(base64.b64decode(writes[0][1]["content"]))
        self.assertEqual(data["signatures"][0]["status"], "revoked")
        self.assertEqual(client.statuses()[-1], (SHA, "failure"))

    def test_cas_conflict_never_reports_signature_success(self):
        client = FakeGitHub()
        client.responses[("PUT", PREFIX + "/contents/" + POLICY.signatures_path)] = GitHubError(409)
        event = self.event() | {"action": "created", "comment": {"id": 201}, "issue": {"number": 7, "pull_request": {"url": "unused"}}}
        with self.assertRaises(GitHubError):
            SignatureGate(client, POLICY, document_revision="d" * 40).run("issue_comment", event)
        self.assertEqual(client.statuses(), [(SHA, "pending"), (SHA, "error")])

    def test_new_signature_requires_confirmed_write_before_success(self):
        event = self.event() | {"action": "created", "comment": {"id": 201}, "issue": {"number": 7, "pull_request": {"url": "unused"}}}
        client = FakeGitHub()
        SignatureGate(client, POLICY, document_revision="d" * 40).run("issue_comment", event)
        write_index = next(index for index, (method, _, _) in enumerate(client.calls) if method == "PUT")
        success_index = next(index for index, (method, path, body) in enumerate(client.calls) if method == "POST" and "/statuses/" in path and body["state"] == "success")
        self.assertLess(write_index, success_index)
        client = FakeGitHub()
        client.responses[("PUT", PREFIX + "/contents/" + POLICY.signatures_path)] = {}
        with self.assertRaises(ValueError):
            SignatureGate(client, POLICY, document_revision="d" * 40).run("issue_comment", event)
        self.assertEqual(client.statuses()[-1], (SHA, "error"))

    def test_mutable_document_revision_is_rejected(self):
        with self.assertRaises(ValueError):
            SignatureGate(FakeGitHub(), POLICY, document_revision="main")

    def test_head_change_never_approves_new_head(self):
        client = FakeGitHub([record()])
        count = 0
        def response():
            nonlocal count
            count += 1
            return pull(head="c" * 40 if count == 3 else SHA)
        client.responses[("GET", PREFIX + "/pulls/7")] = response
        SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertEqual(client.statuses()[-1], (SHA, "failure"))
        self.assertNotIn(("c" * 40, "success"), client.statuses())

    def test_wrong_repository_identity_never_writes_status_or_ledger(self):
        client = FakeGitHub()
        client.responses[("GET", PREFIX)]["id"] += 1
        with self.assertRaises(ValueError):
            SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertFalse(any(method != "GET" for method, _, _ in client.calls))

    def test_comment_permission_error_reports_original_stage_after_error_status(self):
        client = FakeGitHub()
        client.responses[("POST", PREFIX + "/issues/7/comments")] = GitHubError(403, "Sensitive server response")
        with self.assertRaises(GitHubError) as failure:
            SignatureGate(client, POLICY, document_revision="d" * 40).run("schedule", self.event())
        self.assertEqual(failure.exception.stage, "instructions_create")
        self.assertEqual(client.statuses(), [(SHA, "pending"), (SHA, "error")])
        diagnostic = runpy.run_path(str(ROOT / "scripts/cla.py"))["error_diagnostics"]
        self.assertEqual(diagnostic(failure.exception), {
            "error": "GitHubError", "http_status": 403, "stage": "instructions_create",
        })

    def test_cli_diagnostics_never_include_error_body_or_arbitrary_stage(self):
        diagnostic = runpy.run_path(str(ROOT / "scripts/cla.py"))["error_diagnostics"]
        error = GitHubError(429, "synthetic-secret-body")
        error.stage = "synthetic-secret-stage"
        self.assertEqual(diagnostic(error), {"error": "GitHubError", "http_status": 429, "stage": "startup"})
        self.assertEqual(diagnostic(ValueError("synthetic-secret-body")), {"error": "ValueError"})


class Response(BytesIO):
    status = 200


class Opener:
    def __init__(self, value=b"{}", error=None):
        self.value, self.error, self.requests = value, error, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return Response(self.value)


class TransportTests(unittest.TestCase):
    def test_empty_put_uses_zero_length_body_without_permission_parameters(self):
        class RecordingHTTPSHandler(urllib.request.HTTPSHandler):
            def __init__(self):
                super().__init__()
                self.requests = []

            def https_open(self, request):
                self.requests.append(request)
                response = urllib.response.addinfourl(
                    BytesIO(b""), {}, request.full_url, code=204,
                )
                response.msg = "No Content"
                return response

        # Exercise urllib's real header preparation, then stop before socket I/O.
        handler = RecordingHTTPSHandler()
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(), handler,
        )
        result = GitHubClient("synthetic-token", opener=opener).request(
            "PUT", "/repos/fixture/repository/collaborators/fixture-user",
        )
        self.assertIsNone(result)
        self.assertEqual(len(handler.requests), 1)
        request = handler.requests[0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.data, b"")
        self.assertEqual(request.get_header("Content-length"), "0")
        self.assertFalse(request.has_header("Transfer-encoding"))

    def test_requests_use_fixed_api_origin_and_bounded_timeout(self):
        opener = Opener()
        client = GitHubClient("synthetic-token", opener=opener)
        self.assertEqual(client.request("GET", "/repos/fixture/repository"), {})
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/fixture/repository")
        self.assertEqual(timeout, 20)
        for path in ("https://example.invalid/x", "//example.invalid/x", "/foo#bar", "/foo\r\nHeader: value", "/\\evil"):
            with self.assertRaises(ValueError):
                client.request("GET", path)

    def test_redirect_is_not_followed_or_reported_with_sensitive_url(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.invalid"))
        opener = Opener(error=urllib.error.HTTPError("https://api.github.com/x", 302, "Found", {"Location": "https://example.invalid/secret"}, None))
        with self.assertRaises(GitHubError) as failure:
            GitHubClient("synthetic-token", opener=opener).request("GET", "/x")
        self.assertEqual(failure.exception.status, 302)
        self.assertNotIn("secret", str(failure.exception))
        self.assertEqual(len(opener.requests), 1)

    def test_response_size_and_pagination_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            GitHubClient("synthetic-token", opener=Opener(b"x" * (2 * 1024 * 1024 + 1))).request("GET", "/x")
        opener = Opener(json.dumps([{}] * 100).encode())
        with self.assertRaisesRegex(ValueError, "pagination limit"):
            GitHubClient("synthetic-token", opener=opener).paginate("/x?state=open", max_pages=2)
        self.assertEqual(len(opener.requests), 2)
        with self.assertRaises(ValueError):
            GitHubClient("synthetic-token", opener=opener).paginate("/x?page=2")


if __name__ == "__main__":
    unittest.main()
