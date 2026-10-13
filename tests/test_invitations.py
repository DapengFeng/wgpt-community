"""Offline invitation contracts against a persistent, CAS-checked GitHub fixture."""

import base64
import copy
import hashlib
import io
import json
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import invite_collaborators as invitations
from cla.github import GitHubClient, GitHubError
from cla.policy import Policy
from cla.signatures import revoke


def fixture_policy():
    return Policy.from_dict({
        "schema_version": 1,
        "repository": "DapengFeng/wgpt-community",
        "target_repository": "DapengFeng/wgpt",
        "source_repository_id": 1416356927,
        "target_repository_id": 1415618575,
        "cla_version": "1",
        "document_path": "CLA.md",
        "document_sha256": "a" * 64,
        "signatures_branch": "cla-signatures",
        "signatures_path": "signatures/v1.json",
    })


def blob_sha(raw):
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def json_file(value, path, raw=None):
    raw = json.dumps(value).encode() if raw is None else raw
    return {
        "type": "file", "encoding": "base64", "sha": blob_sha(raw),
        "path": path, "content": base64.b64encode(raw).decode(),
    }


class MemoryGitHub(GitHubClient):
    """Use the production paginator while denying all real network access."""

    def __init__(self, server, side):
        super().__init__("synthetic-" + side + "-token")
        self.server, self.side = server, side

    def request(self, method, path, body=None):
        return self.server.request(self.side, method, path, body)


class GitHubFixture:
    """Share API state across runs; failed journal writes cannot become durable."""

    def __init__(self):
        self.policy = fixture_policy()
        self.source = f"/repos/{self.policy.repository}"
        self.target = f"/repos/{self.policy.target_repository}"
        self.journal_path = self.source + "/contents/invitations/v1.json"
        self.records, self.accounts, self.comments, self.pulls = [], {}, {}, {}
        self.reviews = {}
        self.collaborators, self.pending, self.calls = [], [], []
        self.journal_data, self.journal_sha, self.journal_raw = None, None, None
        self.journal_writes = 0
        self.journal_ack_override = None
        self.journal_read_override = None
        self.fail_journal_write = None
        self.invite_failure = None
        self.before_request = None
        self.repository_values = {
            self.source: {
                "id": self.policy.source_repository_id,
                "full_name": self.policy.repository, "private": False,
                "owner": {"type": "User", "id": 18318646},
            },
            self.target: {
                "id": self.policy.target_repository_id,
                "full_name": self.policy.target_repository, "private": True,
                "owner": {"type": "User", "id": 18318646},
            },
        }
        self.public, self.private = MemoryGitHub(self, "public"), MemoryGitHub(self, "private")

    def sign(self, user_id=11, comment_id=None, login=None):
        comment_id = comment_id or user_id + 1000
        login = login or f"contributor-{user_id}"
        timestamp = "2026-01-01T00:00:00Z"
        record = {
            "user_id": user_id, "login": login, "comment_id": comment_id,
            "pull_request": comment_id, "created_at": timestamp,
            "updated_at": timestamp, "cla_version": self.policy.cla_version,
            "document_sha256": self.policy.document_sha256, "status": "active",
        }
        account = {"id": user_id, "login": login, "type": "User"}
        self.accounts[user_id] = copy.deepcopy(account)
        self.comments[comment_id] = {
            "id": comment_id, "user": copy.deepcopy(account),
            "body": self.policy.statement, "created_at": timestamp, "updated_at": timestamp,
            "issue_url": f"https://api.github.com{self.source}/issues/{comment_id}",
        }
        self.pulls[comment_id] = {
            "number": comment_id, "user": copy.deepcopy(account),
            "base": {"ref": "main", "repo": {"id": self.policy.source_repository_id}},
            "head": {"sha": "a" * 40}, "state": "open", "draft": False,
        }
        self.records.append(record)
        self.reviews[comment_id] = []
        return record

    def approve(self, record, **fields):
        review = {
            "id": 9000 + len(self.reviews[record["pull_request"]]),
            "user": {"id": 18318646, "login": "DapengFeng", "type": "User"},
            "state": "APPROVED", "commit_id": self.pulls[record["pull_request"]]["head"]["sha"],
            "submitted_at": "2026-01-01T00:01:00Z",
            "pull_request_url": f"https://api.github.com{self.source}/pulls/{record['pull_request']}",
            **fields,
        }
        self.reviews[record["pull_request"]].append(review)
        return review

    def sign_and_approve(self, *args, **kwargs):
        record = self.sign(*args, **kwargs)
        self.approve(record)
        return record

    def invitation(self, user_id, invitation_id=500, **extra):
        return {
            "id": invitation_id,
            "invitee": {"id": user_id, "login": f"contributor-{user_id}"},
            "repository": {"id": self.policy.target_repository_id},
            "permissions": "write", **extra,
        }

    def store_journal(self, attempts, raw=None):
        self.journal_data = {"schema_version": 1, "attempts": copy.deepcopy(attempts)}
        if raw is None:
            raw = (json.dumps(self.journal_data, indent=2) + "\n").encode()
        self.journal_raw, self.journal_sha = raw, blob_sha(raw)

    def attempt(self, user_id, comment_id, status="invited", *, age_hours=1, **extra):
        return {
            "user_id": user_id, "comment_id": comment_id, "status": status,
            "request_intent": status not in {"existing_access", "existing_invitation"},
            "cla_version": self.policy.cla_version,
            "document_sha256": self.policy.document_sha256,
            "attempted_at": (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z"),
            **extra,
        }

    def mutations(self, *, side=None, method=None):
        return [call for call in self.calls if call[1] != "GET"
                and (side is None or call[0] == side)
                and (method is None or call[1] == method)]

    def run(self, *, apply=True):
        return invitations.InvitationReconciler(
            self.public, self.private, self.policy, apply=apply,
        ).run()

    def request(self, side, method, path, body):
        self.calls.append((side, method, path, copy.deepcopy(body)))
        if self.before_request:
            self.before_request(side, method, path, body)
        parsed = urlsplit(path)
        route, query = parsed.path, parse_qs(parsed.query)
        expected_side = "private" if route.startswith(self.target + "/") or route == self.target else "public"
        if side != expected_side:
            raise AssertionError(f"Credential crossed repository boundary: {side} {route}")
        if method == "GET":
            if route in self.repository_values:
                return copy.deepcopy(self.repository_values[route])
            if route == self.source + "/branches/cla-signatures":
                return {"name": "cla-signatures"}
            if route == self.source + "/contents/signatures/v1.json":
                if query != {"ref": ["cla-signatures"]}:
                    raise AssertionError("Signature branch was not selected")
                return json_file(
                    {"schema_version": 1, "signatures": self.records},
                    self.policy.signatures_path,
                )
            if route == self.journal_path:
                if query != {"ref": ["cla-signatures"]}:
                    raise AssertionError("Journal branch was not selected")
                if self.journal_data is None:
                    raise GitHubError(404)
                file = json_file(self.journal_data, "invitations/v1.json", self.journal_raw)
                if self.journal_read_override:
                    file.update(self.journal_read_override)
                return file
            if route.startswith(self.source + "/issues/comments/"):
                comment = self.comments.get(int(route.rsplit("/", 1)[1]))
                if comment is None:
                    raise GitHubError(404)
                return copy.deepcopy(comment)
            if route.endswith("/reviews"):
                start = (int(query["page"][0]) - 1) * 100
                return copy.deepcopy(self.reviews[int(route.split("/")[-2])][start:start + 100])
            if route.startswith(self.source + "/pulls/"):
                return copy.deepcopy(self.pulls[int(route.rsplit("/", 1)[1])])
            if route.startswith("/user/"):
                return copy.deepcopy(self.accounts[int(route.rsplit("/", 1)[1])])
            if route in {self.target + "/collaborators", self.target + "/invitations"}:
                if query.get("per_page") != ["100"] or len(query.get("page", [])) != 1:
                    raise AssertionError("Production paginator must supply bounded pages")
                values = self.collaborators if route.endswith("/collaborators") else self.pending
                start = (int(query["page"][0]) - 1) * 100
                return copy.deepcopy(values[start:start + 100])
        if method == "PUT" and route == self.journal_path:
            self.journal_writes += 1
            if self.fail_journal_write == self.journal_writes:
                raise GitHubError(409)
            if body.get("branch") != "cla-signatures" or body.get("sha") != self.journal_sha:
                raise GitHubError(409, "Journal compare-and-swap failed")
            raw = base64.b64decode(body["content"], validate=True)
            payload = json.loads(raw)
            self.store_journal(payload["attempts"], raw)
            acknowledgement = {"sha": self.journal_sha, "path": "invitations/v1.json"}
            if self.journal_ack_override:
                acknowledgement.update(self.journal_ack_override)
            return {"content": acknowledgement}
        if method == "PUT" and route.startswith(self.target + "/collaborators/"):
            if body is not None:
                raise AssertionError("Personal repository invitations must omit role parameters")
            if self.journal_data is None or self.journal_data["attempts"][-1]["status"] != "attempted":
                raise AssertionError("Invitation was sent before durable intent")
            login = route.rsplit("/", 1)[1]
            user = next(account for account in self.accounts.values() if account["login"] == login)
            result = self.invitation(user["id"], 500 + len(self.pending))
            self.pending.append(result)
            if self.invite_failure == "after_creation":
                self.invite_failure = None
                raise GitHubError(0, "GitHub transport failed")
            if self.invite_failure == "identity":
                result = {**result, "invitee": {"id": user["id"] + 1}}
            return copy.deepcopy(result)
        if method == "DELETE" and route.startswith(self.target + "/invitations/"):
            invitation_id = int(route.rsplit("/", 1)[1])
            self.pending = [item for item in self.pending if item["id"] != invitation_id]
            return None
        raise AssertionError(f"Unexpected fixture request: {method} {path}")


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHubFixture()
        self.record = self.api.sign()

    def test_signature_alone_waits_without_spending_an_invitation_attempt(self):
        for apply in (False, True):
            self.assertEqual(self.api.run(apply=apply), [{"user_id": 11, "status": "human_approval_required"}])
            self.assertEqual(self.api.mutations(), [])
        self.api.approve(self.record)
        self.assertEqual(self.api.run()[0]["status"], "invited")

    def test_only_the_human_public_repository_owner_can_approve(self):
        for user in (
            {"id": 11, "login": "DapengFeng", "type": "User"},
            {"id": 99, "login": "DapengFeng", "type": "User"},
            {"id": 18318646, "login": "DapengFeng", "type": "Bot"},
        ):
            with self.subTest(user=user):
                api = GitHubFixture()
                record = api.sign()
                api.approve(record, user=user, author_association="OWNER")
                self.assertEqual(api.run()[0]["status"], "human_approval_required")
                self.assertEqual(api.mutations(), [])

    def test_owner_cannot_approve_their_own_application(self):
        api = GitHubFixture()
        api.sign_and_approve(18318646)
        self.assertEqual(api.run()[0]["status"], "human_approval_required")
        self.assertEqual(api.mutations(), [])

    def test_approval_must_follow_the_current_signature_and_match_current_head(self):
        for fields in (
            {"submitted_at": "2025-12-31T23:59:59Z"},
            {"submitted_at": self.record["created_at"]},
            {"commit_id": "b" * 40},
        ):
            with self.subTest(fields=fields):
                self.api.reviews[self.record["pull_request"]] = []
                self.api.approve(self.record, **fields)
                self.assertEqual(self.api.run()[0]["status"], "human_approval_required")
                self.assertEqual(self.api.mutations(), [])

    def test_new_signature_cannot_reuse_an_earlier_approval(self):
        api = GitHubFixture()
        record = api.sign_and_approve()
        record["created_at"] = record["updated_at"] = "2026-01-01T00:02:00Z"
        api.comments[record["comment_id"]].update(created_at=record["created_at"], updated_at=record["updated_at"])
        self.assertEqual(api.run()[0]["status"], "human_approval_required")
        self.assertEqual(api.mutations(), [])

    def test_closed_draft_or_wrong_base_pr_cannot_authorize_access(self):
        for fields in (
            {"state": "closed"}, {"draft": True},
            {"base": {"ref": "other", "repo": {"id": self.api.policy.source_repository_id}}},
        ):
            with self.subTest(fields=fields):
                api = GitHubFixture()
                record = api.sign_and_approve()
                api.pulls[record["pull_request"]].update(fields)
                self.assertEqual(api.run()[0]["status"], "human_approval_required")
                self.assertEqual(api.mutations(), [])

    def test_latest_decision_wins_without_reviving_old_approval(self):
        for state in ("CHANGES_REQUESTED", "DISMISSED"):
            with self.subTest(state=state):
                api = GitHubFixture()
                record = api.sign_and_approve()
                api.approve(record, state=state)
                api.approve(record, state="COMMENTED")
                self.assertEqual(api.run()[0]["status"], "human_approval_required")
                self.assertEqual(api.mutations(), [])
                api.approve(record)
                self.assertEqual(api.run()[0]["status"], "invited")

    def test_comment_or_unsubmitted_review_does_not_grant_or_revoke_approval(self):
        for state in ("COMMENTED", "PENDING"):
            with self.subTest(state=state):
                api = GitHubFixture()
                record = api.sign()
                api.approve(record, state=state)
                self.assertEqual(api.run()[0]["status"], "human_approval_required")
                api.approve(record)
                api.approve(record, state=state)
                self.assertEqual(api.run()[0]["status"], "invited")

    def test_owner_is_identified_by_id_not_login(self):
        self.api.approve(self.record, user={"id": 18318646, "type": "User", "login": "renamed-owner"})
        self.assertEqual(self.api.run()[0]["status"], "invited")

    def test_saved_intent_contains_the_approval_evidence(self):
        review = self.api.approve(self.record)
        self.api.run()
        self.assertEqual(self.api.journal_data["attempts"][0]["approval"], {
            "pull_request": self.record["pull_request"], "review_id": review["id"],
            "reviewer_id": 18318646, "head_sha": "a" * 40,
            "submitted_at": review["submitted_at"],
        })

    def test_pending_owned_invitation_cancelled_when_approval_is_dismissed(self):
        review = self.api.approve(self.record)
        self.api.run()
        review["state"] = "DISMISSED"
        self.assertEqual([e["status"] for e in self.api.run()], ["cancelled", "human_approval_required"])
        self.assertEqual(self.api.pending, [])
        self.assertEqual(len(self.api.mutations(side="private", method="DELETE")), 1)
        self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="DELETE")), 1)

    def test_missing_approval_never_removes_accepted_or_external_access(self):
        for existing in ("accepted", "external"):
            with self.subTest(existing=existing):
                api = GitHubFixture()
                record = api.sign_and_approve()
                if existing == "accepted":
                    api.run()
                    api.pending.clear()
                    api.collaborators = [{"id": 11}]
                else:
                    api.pending = [api.invitation(11)]
                baseline = len(api.mutations(side="private"))
                api.reviews[record["pull_request"]].clear()
                api.run()
                self.assertEqual(len(api.mutations(side="private")), baseline)

    def test_review_read_failure_is_not_revocation_or_permission(self):
        self.api.approve(self.record)
        self.api.run()
        baseline = len(self.api.mutations())

        def forbid_reviews(side, method, path, body):
            if "/reviews?" in path:
                raise GitHubError(403)

        self.api.before_request = forbid_reviews
        with self.assertRaises(GitHubError):
            self.api.run()
        self.assertEqual(len(self.api.mutations()), baseline)

    def test_review_pagination_observes_a_later_change_request(self):
        self.api.approve(self.record)
        for _ in range(99):
            self.api.approve(self.record, state="COMMENTED")
        self.api.approve(self.record, state="CHANGES_REQUESTED")
        self.assertEqual(self.api.run()[0]["status"], "human_approval_required")
        self.assertTrue(any("reviews?per_page=100&page=2" in c[2] for c in self.api.calls))
        self.assertEqual(self.api.mutations(), [])

    def test_review_evidence_cannot_point_at_another_pr(self):
        self.api.approve(self.record, pull_request_url="https://api.github.com/repos/other/project/pulls/1")
        with self.assertRaisesRegex(ValueError, "different pull request"):
            self.api.run()
        self.assertEqual(self.api.mutations(), [])

    def test_incomplete_or_malformed_reviews_fail_before_any_mutation(self):
        for problem in ("page_limit", "unknown_state", "duplicate_id", "bad_date", "missing_user"):
            with self.subTest(problem=problem):
                api = GitHubFixture()
                record = api.sign_and_approve()
                review = api.reviews[record["pull_request"]][0]
                if problem == "page_limit":
                    for _ in range(999):
                        api.approve(record, state="COMMENTED")
                elif problem == "unknown_state":
                    review["state"] = "UNRECOGNIZED"
                elif problem == "duplicate_id":
                    api.approve(record, id=review["id"])
                elif problem == "bad_date":
                    review["submitted_at"] = None
                else:
                    review["user"] = None
                with self.assertRaises(ValueError):
                    api.run()
                self.assertEqual(api.mutations(), [])

    def test_failure_for_another_applicant_stops_all_invitation_side_effects(self):
        self.api.approve(self.record)
        another = self.api.sign_and_approve(12)
        self.api.reviews[another["pull_request"]][0]["state"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            self.api.run()
        self.assertEqual(self.api.mutations(), [])

    def test_head_change_during_review_read_blocks_invitation(self):
        self.api.approve(self.record)

        def change_head(side, method, path, body):
            if "/reviews?" in path:
                self.api.pulls[self.record["pull_request"]]["head"]["sha"] = "b" * 40

        self.api.before_request = change_head
        self.assertEqual(self.api.run()[0]["status"], "human_approval_required")
        self.assertEqual(self.api.mutations(), [])

    def test_dismissal_before_intent_or_during_journal_write_blocks_put(self):
        for stage in ("recheck", "intent"):
            with self.subTest(stage=stage):
                api = GitHubFixture()
                record = api.sign_and_approve()
                reads = 0

                def dismiss_review(side, method, path, body, stage=stage, api=api, record=record):
                    nonlocal reads
                    if "/reviews?" in path:
                        reads += 1
                    if ((stage == "recheck" and reads == 2)
                        or (stage == "intent" and method == "PUT" and path == api.journal_path)):
                        api.reviews[record["pull_request"]][0]["state"] = "DISMISSED"

                api.before_request = dismiss_review
                expected = "human_approval_required" if stage == "recheck" else "authorization_changed_before_invitation"
                self.assertEqual(api.run()[0]["status"], expected)
                self.assertEqual(api.mutations(side="private"), [])

    def test_journal_does_not_accept_intent_without_approval_or_corrupt_evidence(self):
        journal = invitations.InvitationJournal(self.api.public, self.api.policy)
        with self.assertRaisesRegex(ValueError, "requires maintainer approval"):
            journal.begin(self.record, "attempted")
        self.assertEqual(self.api.mutations(), [])
        self.api.store_journal([self.api.attempt(11, self.record["comment_id"], approval={})])
        with self.assertRaisesRegex(ValueError, "approval evidence"):
            self.api.run()
        self.assertEqual(self.api.mutations(), [])

    def test_new_signature_during_run_invalidates_old_approval(self):
        for stage in ("inventory", "account", "intent"):
            with self.subTest(stage=stage):
                api = GitHubFixture()
                api.sign_and_approve()
                changed = False

                def replace_signature(side, method, path, body, stage=stage, api=api):
                    nonlocal changed
                    trigger = {
                        "inventory": method == "GET" and "/collaborators?" in path,
                        "account": method == "GET" and path == "/user/11",
                        "intent": method == "PUT" and path == api.journal_path,
                    }[stage]
                    if trigger and not changed:
                        changed = True
                        fresh = api.sign(11, comment_id=2000)
                        fresh["created_at"] = fresh["updated_at"] = "2026-01-01T00:02:00Z"
                        api.comments[2000].update(created_at=fresh["created_at"], updated_at=fresh["updated_at"])

                api.before_request = replace_signature
                if stage == "inventory":
                    with self.assertRaisesRegex(ValueError, "ledger changed"):
                        api.run()
                else:
                    expected = "signature_no_longer_valid" if stage == "account" else "authorization_changed_before_invitation"
                    self.assertEqual(api.run()[0]["status"], expected)
                self.assertEqual(api.mutations(side="private"), [])

    def test_incomplete_pull_response_does_not_cancel_pending_invitation(self):
        for field in ("draft", "head", "state", "base", "user"):
            with self.subTest(field=field):
                api = GitHubFixture()
                record = api.sign_and_approve()
                api.run()
                baseline = len(api.mutations())
                del api.pulls[record["pull_request"]][field]
                with self.assertRaisesRegex(ValueError, "approval pull request"):
                    api.run()
                self.assertEqual(len(api.mutations()), baseline)
                self.assertEqual(len(api.pending), 1)

    def test_withdrawal_after_intent_still_consumes_run_and_daily_budgets(self):
        for recent_count, expected in ((0, 10), (39, 1)):
            with self.subTest(recent_count=recent_count):
                api = GitHubFixture()
                for user_id in range(11, 54):
                    api.sign_and_approve(user_id)
                api.store_journal([
                    api.attempt(user_id, user_id + 1000, "accepted")
                    for user_id in range(100, 100 + recent_count)
                ])

                def withdraw_written_intent(side, method, path, body, api=api):
                    if method == "PUT" and path == api.journal_path:
                        entries = json.loads(base64.b64decode(body["content"]))["attempts"]
                        current = entries[-1]
                        if current["status"] == "attempted":
                            api.reviews[current["approval"]["pull_request"]][0]["state"] = "DISMISSED"

                api.before_request = withdraw_written_intent
                api.run()
                self.assertEqual(len(api.journal_data["attempts"]), recent_count + expected)
                self.assertEqual(api.mutations(side="private"), [])


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHubFixture()
        self.record = self.api.sign_and_approve()

    def test_invites_once_and_persists_intent_before_api_write(self):
        self.assertEqual(self.api.run(), [{"user_id": 11, "status": "invited"}])
        self.assertEqual(self.api.run(), [{"user_id": 11, "status": "existing_invitation"}])
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)
        self.assertIsNone(self.api.mutations(side="private", method="PUT")[0][3])
        self.assertEqual(self.api.journal_data["attempts"][0]["invitation_id"], 500)
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "invited")

    def test_existing_access_and_external_invitation_never_change_permissions(self):
        for existing in ("access", "invitation"):
            with self.subTest(existing=existing):
                api = GitHubFixture()
                api.sign_and_approve()
                if existing == "access":
                    api.collaborators = [{"id": 11, "role_name": "admin"}]
                else:
                    api.pending = [api.invitation(11, permissions="admin")]
                self.assertEqual(api.run()[0]["status"], "existing_" + existing)
                self.assertEqual(api.mutations(side="private"), [])

    def test_accepted_invitation_is_recorded_without_another_put(self):
        self.api.run()
        self.api.pending.clear()
        self.api.collaborators = [{"id": 11}]
        self.api.run()
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "accepted")
        self.assertEqual(len(self.api.mutations(side="private")), 1)

    def test_renamed_account_uses_current_login_resolved_by_id(self):
        self.api.accounts[11]["login"] = "new-login"
        self.api.run()
        put = self.api.mutations(side="private", method="PUT")[0]
        self.assertTrue(put[2].endswith("/collaborators/new-login"))
        self.assertIn(("public", "GET", "/user/11", None), self.api.calls)

    def test_changed_resolved_identity_stops_before_writes(self):
        self.api.accounts[11]["id"] = 99
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.api.run()
        self.assertEqual(self.api.mutations(), [])

    def test_invalid_signature_evidence_never_invites(self):
        for change in ("deleted", "edited", "author", "body", "wrong_repository", "revoked", "version"):
            with self.subTest(change=change):
                api = GitHubFixture()
                record = api.sign_and_approve()
                comment = api.comments[record["comment_id"]]
                if change == "deleted":
                    api.comments.clear()
                elif change == "edited":
                    comment["updated_at"] = "2026-01-01T01:00:00Z"
                elif change == "author":
                    comment["user"]["id"] = 99
                elif change == "body":
                    comment["body"] = "Please invite @other-account; $(echo unsafe)"
                elif change == "wrong_repository":
                    api.pulls[record["pull_request"]]["base"]["repo"]["id"] = 1
                elif change == "revoked":
                    revoke(record, "comment_deleted")
                else:
                    record["cla_version"] = "2"
                self.assertEqual(api.run(), [])
                self.assertEqual(api.mutations(), [])

    def test_latest_withdrawal_does_not_reactivate_older_signature(self):
        newer = self.api.sign_and_approve(11, comment_id=2000)
        revoke(newer, "comment_edited")
        self.assertEqual(self.api.run(), [])
        self.assertEqual(self.api.mutations(), [])

    def test_rechecks_evidence_before_intent_and_put(self):
        reads = 0

        def withdraw_on_recheck(side, method, path, body):
            nonlocal reads
            if method == "GET" and "/issues/comments/" in path:
                reads += 1
                if reads == 2:
                    self.api.comments.clear()

        self.api.before_request = withdraw_on_recheck
        self.assertEqual(self.api.run()[0]["status"], "signature_no_longer_valid")
        self.assertEqual(self.api.mutations(), [])

    def test_failed_intent_commit_prevents_invitation(self):
        self.api.fail_journal_write = 1
        with self.assertRaises(GitHubError):
            self.api.run()
        self.assertIsNone(self.api.journal_data)
        self.assertEqual(self.api.mutations(side="private"), [])

    def test_journal_compare_and_swap_rejects_concurrent_writer(self):
        self.api.store_journal([])
        journal = invitations.InvitationJournal(self.api.public, self.api.policy)
        journal.load()
        self.api.store_journal([self.api.attempt(22, 2222)])
        with self.assertRaises(GitHubError):
            approval = invitations.ApprovalGate(self.api.public, self.api.policy, 18318646).read(self.record)
            journal.begin(self.record, "attempted", approval=approval)
        self.assertEqual(self.api.journal_data["attempts"][0]["user_id"], 22)
        self.assertEqual(self.api.mutations(side="private"), [])

    def test_wrong_journal_acknowledgement_prevents_invitation(self):
        for fields in ({"sha": "b" * 40}, {"path": "other.json"}, {"path": None}):
            with self.subTest(fields=fields):
                api = GitHubFixture()
                api.sign_and_approve()
                api.journal_ack_override = fields
                with self.assertRaisesRegex(ValueError, "acknowledged"):
                    api.run()
                self.assertEqual(api.mutations(side="private"), [])

    def test_timeout_after_creation_reconciles_inventory_without_reinviting(self):
        self.api.invite_failure = "after_creation"
        with self.assertRaises(GitHubError):
            self.api.run()
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "attempted")
        start = len(self.api.calls)
        self.assertEqual(self.api.run()[0]["status"], "existing_invitation")
        self.assertTrue(any("/invitations?" in call[2] for call in self.api.calls[start:]))
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)

    def test_failed_result_commit_does_not_duplicate_successful_invitation(self):
        self.api.fail_journal_write = 2
        with self.assertRaises(GitHubError):
            self.api.run()
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "attempted")
        self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)

    def test_rejected_invitation_preserves_intent_without_automatic_retry(self):
        for status in (403, 422, 429):
            with self.subTest(status=status):
                api = GitHubFixture()
                api.sign_and_approve()

                def reject_put(side, method, path, body, status=status):
                    if side == "private" and method == "PUT":
                        raise GitHubError(status)

                api.before_request = reject_put
                with self.assertRaises(GitHubError):
                    api.run()
                self.assertEqual(api.pending, [])
                self.assertEqual(api.journal_data["attempts"][0]["status"], "attempted")
                api.before_request = None
                self.assertEqual(api.run()[0]["status"], "prior_attempt_requires_new_request")
                self.assertEqual(len(api.mutations(side="private", method="PUT")), 1)

    def test_identity_mismatch_is_retained_and_never_blindly_retried(self):
        self.api.invite_failure = "identity"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.api.run()
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "unresolved")
        self.api.pending.clear()
        self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)

    def test_expired_or_declined_invitation_requires_fresh_comment(self):
        self.api.run()
        self.api.pending.clear()
        self.assertEqual(self.api.run()[0]["status"], "prior_attempt_requires_new_request")
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "expired_or_declined")
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)
        self.api.sign_and_approve(11, comment_id=2000)
        self.assertEqual(self.api.run()[0]["status"], "invited")
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 2)

    def test_ambiguous_attempt_without_inventory_needs_fresh_request(self):
        self.api.store_journal([self.api.attempt(11, self.record["comment_id"], "attempted")])
        self.assertEqual(self.api.run()[0]["status"], "prior_attempt_requires_new_request")
        self.assertEqual(self.api.mutations(side="private"), [])

    def test_withdrawal_cancels_only_exact_owned_pending_invitation(self):
        self.api.run()
        revoke(self.record, "comment_deleted")
        self.assertEqual(self.api.run()[0]["status"], "cancelled")
        deletes = self.api.mutations(side="private", method="DELETE")
        self.assertEqual([call[2] for call in deletes], [self.api.target + "/invitations/500"])
        self.assertEqual(self.api.pending, [])
        self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="DELETE")), 1)

    def test_withdrawal_does_not_remove_access_or_an_unowned_invitation(self):
        for state in ("accepted", "replaced", "unknown_owner", "external"):
            with self.subTest(state=state):
                api = GitHubFixture()
                record = api.sign_and_approve()
                if state == "external":
                    api.pending = [api.invitation(11)]
                else:
                    status = "attempted" if state == "unknown_owner" else "invited"
                    fields = {} if state == "unknown_owner" else {"invitation_id": 500}
                    api.store_journal([api.attempt(11, record["comment_id"], status, **fields)])
                    if state == "accepted":
                        api.collaborators = [{"id": 11}]
                    else:
                        api.pending = [api.invitation(11, 501)]
                revoke(record, "comment_deleted")
                api.run()
                self.assertEqual(api.mutations(side="private"), [])

    def test_dry_run_never_writes_invitations_or_journal(self):
        self.assertEqual(self.api.run(apply=False)[0]["status"], "would_invite")
        self.assertEqual(self.api.mutations(), [])
        self.api.store_journal([self.api.attempt(11, self.record["comment_id"], invitation_id=500)])
        self.api.pending = [self.api.invitation(11)]
        revoke(self.record, "comment_deleted")
        self.assertEqual(self.api.run(apply=False)[0]["status"], "would_cancel")
        self.assertEqual(self.api.mutations(), [])
        self.assertEqual(self.api.journal_data["attempts"][0]["status"], "invited")

    def test_repository_identity_and_visibility_mismatches_stop_all_writes(self):
        for side in ("source", "target"):
            for key, value in (("id", 99), ("full_name", "attacker/other"), ("private", side == "source")):
                with self.subTest(side=side, key=key):
                    api = GitHubFixture()
                    api.sign_and_approve()
                    api.repository_values[getattr(api, side)][key] = value
                    with self.assertRaisesRegex(ValueError, "identity or visibility"):
                        api.run()
                    self.assertEqual(api.mutations(), [])

    def test_nonpersonal_target_owner_is_rejected_without_side_effects(self):
        for owner in ({"type": "Organization"}, {"type": "Bot"}, {}):
            with self.subTest(owner=owner):
                api = GitHubFixture()
                api.sign_and_approve()
                api.repository_values[api.target]["owner"] = owner
                with self.assertRaises(ValueError):
                    api.run()
                self.assertEqual(api.mutations(), [])

    def test_inventory_pagination_finds_existing_access_on_second_page(self):
        self.api.collaborators = [{"id": i} for i in range(100, 200)] + [{"id": 11}]
        self.assertEqual(self.api.run()[0]["status"], "existing_access")
        self.assertTrue(any("collaborators?per_page=100&page=2" in call[2] for call in self.api.calls))
        self.assertEqual(self.api.mutations(side="private"), [])

    def test_inventory_pagination_finds_existing_invitation_on_second_page(self):
        self.api.pending = [self.api.invitation(i, i) for i in range(100, 200)] + [self.api.invitation(11)]
        self.assertEqual(self.api.run()[0]["status"], "existing_invitation")
        self.assertTrue(any("invitations?per_page=100&page=2" in call[2] for call in self.api.calls))
        self.assertEqual(self.api.mutations(side="private"), [])

    def test_incomplete_or_forbidden_inventory_fails_before_any_mutation(self):
        for failure in ("page_limit", "forbidden"):
            with self.subTest(failure=failure):
                api = GitHubFixture()
                api.sign_and_approve()
                api.collaborators = [{"id": i} for i in range(100, 1100)]
                if failure == "forbidden":
                    def forbid_second_page(side, method, path, body):
                        if "collaborators?per_page=100&page=2" in path:
                            raise GitHubError(403)
                    api.before_request = forbid_second_page
                with self.assertRaises((ValueError, GitHubError)):
                    api.run()
                self.assertEqual(api.mutations(), [])

    def test_live_evidence_forbidden_is_not_treated_as_withdrawal(self):
        self.api.run()
        baseline = len(self.api.mutations())

        def forbid_comment(side, method, path, body):
            if "/issues/comments/" in path:
                raise GitHubError(403)

        self.api.before_request = forbid_comment
        with self.assertRaises(GitHubError):
            self.api.run()
        self.assertEqual(len(self.api.mutations()), baseline)

    def test_maximum_ten_new_invitations_per_run(self):
        for user_id in range(12, 24):
            self.api.sign_and_approve(user_id)
        events = self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 10)
        self.assertEqual(sum(event["status"] == "deferred_run_limit" for event in events), 3)

    def test_dry_run_plan_applies_the_same_run_and_daily_limits(self):
        for user_id in range(12, 24):
            self.api.sign_and_approve(user_id)
        events = self.api.run(apply=False)
        self.assertEqual(sum(event["status"] == "would_invite" for event in events), 10)
        self.assertEqual(sum(event["status"] == "deferred_run_limit" for event in events), 3)
        self.api.store_journal([
            self.api.attempt(user_id, user_id + 1000, "accepted")
            for user_id in range(100, 139)
        ])
        events = self.api.run(apply=False)
        self.assertEqual(sum(event["status"] == "would_invite" for event in events), 1)
        self.assertEqual(sum(event["status"] == "deferred_run_limit" for event in events), 12)
        self.assertEqual(self.api.mutations(), [])

    def test_daily_limit_leaves_only_remaining_capacity(self):
        self.api.sign_and_approve(12)
        self.api.sign_and_approve(13)
        self.api.store_journal([
            self.api.attempt(user_id, user_id + 1000, "accepted")
            for user_id in range(100, 139)
        ])
        events = self.api.run()
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)
        self.assertEqual(sum(event["status"] == "deferred_run_limit" for event in events), 2)

    def test_forty_recent_attempts_block_another_invitation(self):
        self.api.store_journal([
            self.api.attempt(user_id, user_id + 1000, "cancelled")
            for user_id in range(100, 140)
        ])
        self.assertEqual(self.api.run()[0]["status"], "deferred_run_limit")
        self.assertEqual(self.api.mutations(), [])

    def test_existing_access_records_do_not_consume_invitation_quota(self):
        self.api.store_journal([
            self.api.attempt(user_id, user_id + 1000, "existing_access")
            for user_id in range(100, 140)
        ])
        self.assertEqual(self.api.run()[0]["status"], "invited")
        self.assertEqual(len(self.api.mutations(side="private", method="PUT")), 1)

    def test_daily_attempts_older_than_twenty_four_hours_do_not_block(self):
        self.api.store_journal([
            self.api.attempt(user_id, user_id + 1000, "accepted", age_hours=25)
            for user_id in range(100, 140)
        ])
        self.assertEqual(self.api.run()[0]["status"], "invited")

    def test_corrupt_journal_is_not_overwritten_or_used_to_invite(self):
        attempt = self.api.attempt(11, 1011, "attempted")
        attempt["attempted_at"] = "invalid"
        self.api.store_journal([attempt])
        with self.assertRaises(ValueError):
            self.api.run()
        self.assertEqual(self.api.mutations(), [])

    def test_journal_read_identity_and_blob_digest_must_match(self):
        for fields in (
            {"type": "symlink"}, {"path": "other.json"},
            {"path": None}, {"sha": "b" * 40},
        ):
            with self.subTest(fields=fields):
                api = GitHubFixture()
                api.sign_and_approve()
                api.store_journal([])
                api.journal_read_override = fields
                with self.assertRaises(ValueError):
                    api.run()
                self.assertEqual(api.mutations(), [])


class InvitationEntryTests(unittest.TestCase):
    def trusted_environment(self):
        return {
            "GITHUB_REPOSITORY_ID": "1416356927",
            "GITHUB_REPOSITORY": "DapengFeng/wgpt-community",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "schedule",
        }

    def test_only_trusted_repository_main_schedule_or_dispatch_can_apply(self):
        environment = self.trusted_environment()
        invitations.require_trusted_workflow(environment)
        environment["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        invitations.require_trusted_workflow(environment)
        for key, values in {
            "GITHUB_REPOSITORY_ID": ("999", ""),
            "GITHUB_REPOSITORY": ("fork/wgpt-community",),
            "GITHUB_REF": ("refs/heads/other", "refs/tags/main", "refs/pull/1/merge"),
            "GITHUB_EVENT_NAME": ("pull_request", "pull_request_target", "issue_comment", "push"),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    invitations.require_trusted_workflow({**environment, key: value})

    def test_untrusted_apply_is_rejected_before_reading_or_constructing_clients(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(sys, "argv", ["invite", "--apply"]),
            patch.object(invitations, "GitHubClient") as client,
            patch.object(invitations, "load_policy") as policy,
        ):
            with self.assertRaises(ValueError):
                invitations.main()
            client.assert_not_called()
            policy.assert_not_called()

    def test_transport_failure_never_echoes_token_or_remote_error_body(self):
        token = "synthetic-sensitive-marker"

        class FailureOpener:
            def open(self, request, *, timeout):
                raise urllib.error.URLError("remote error includes " + token)

        output = io.StringIO()
        with (
            patch("sys.stdout", output), patch("sys.stderr", output),
            self.assertRaises(GitHubError) as captured,
        ):
            GitHubClient(token, opener=FailureOpener()).request("GET", "/repos/example/repo")
        self.assertNotIn(token, str(captured.exception) + output.getvalue())
        self.assertEqual(captured.exception.status, 0)


if __name__ == "__main__":
    unittest.main()
