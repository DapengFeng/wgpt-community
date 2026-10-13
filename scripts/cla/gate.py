"""Trusted-main orchestration; PR data is inspected but never checked out or executed."""

import re
import sys

from .github import GitHubError
from .signatures import (
    apply_comment_event,
    human_account,
    latest_signatures,
    read_ledger,
    record_unseen_comments,
    revoke,
    verify_live_signature,
    write_ledger,
)

CONTEXT = "cla/signature"
API_STAGES = frozenset({
    "repository_lookup", "pull_requests_list", "pull_request_lookup", "status_pending",
    "ledger_read", "comment_event", "comments_list", "commit_authors", "signature_verify",
    "instructions_create", "instructions_update", "ledger_write", "head_recheck", "status_publish",
})


def contributor_ids(client, policy, pull):
    if not human_account(pull.get("user")):
        raise ValueError("A human PR author is required")
    commits = client.paginate(f"/repos/{policy.repository}/pulls/{pull['number']}/commits")
    if not commits or len(commits) != pull.get("commits") or commits[-1].get("sha") != pull["head"]["sha"]:
        raise ValueError("The complete current commit history could not be verified")
    authors = {pull["user"]["id"]}
    for commit in commits:
        author = commit.get("author")
        if not isinstance(author, dict):
            raise TypeError("A commit author has no verified GitHub account")
        if author.get("type") != "Bot":
            if not human_account(author):
                raise ValueError("A commit author has no verified GitHub account")
            authors.add(author["id"])
        message = commit.get("commit", {}).get("message")
        if not isinstance(message, str):
            raise TypeError("A commit has no author metadata")
        # REST exposes only the primary author. Do not silently accept unresolved
        # co-authors until an account-bound co-author lookup is implemented.
        if re.search(r"^\s*co-authored-by\s*:", message, re.IGNORECASE | re.MULTILINE):
            raise ValueError("Co-authors require explicit account verification by the maintainer")
    return authors


class SignatureGate:
    def __init__(self, client, policy, *, document_revision):
        if not isinstance(document_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", document_revision):
            raise ValueError("A trusted source revision is required for the CLA document link")
        self.client = client
        self.policy = policy
        self.prefix = f"/repos/{policy.repository}"
        self.document_url = f"https://github.com/{policy.repository}/blob/{document_revision}/{policy.document_path}"
        self.stage = "repository_lookup"

    def status(self, pull, state, description):
        sha = pull.get("head", {}).get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid pull request head revision")
        self.client.request("POST", f"{self.prefix}/statuses/{sha}", {
            "state": state, "context": CONTEXT, "description": description[:140],
            "target_url": self.document_url,
        })

    def instructions(self, pull, comments):
        marker = "<!-- wgpt-cla-instructions -->"
        body = (
            marker + "\nRead [CLA version " + self.policy.cla_version + "](" + self.document_url + ") before signing. "
            "The PR author must post the entire statement below as a new comment, without code fences. "
            "Every human commit author needs their own valid signature; an existing signature can be reused. "
            "Do not add secrets or private source code to this public PR.\n\n"
            "签署前请阅读上述 CLA。PR 作者须将下方完整声明作为新评论发送，不要附加代码围栏。"
            "每位真人 commit 作者均须已有本人有效签署，旧签署可复用。不要在公开 PR 中添加秘密或私有源码。\n\n"
            "```text\n" + self.policy.statement + "\n```\n\n"
            "Editing or deleting your signing comment revokes its future use. Sign again in a new comment. "
            "The required commit status is `cla/signature`; it does not grant repository access. "
            "After signing, wait for the public repository owner to review and Approve this PR's current revision. "
            "Keep it open until you accept the invitation; new commits need a new approval.\n\n"
            "修改或删除签署评论会撤销后续使用资格，恢复时须发布新的签署评论。"
            "必需的提交状态为 `cla/signature`，它不授予仓库访问权。"
            "签署后，等待公开仓库所有者审阅并 Approve 本 PR 的当前版本。"
            "接受邀请前请保持 PR 开放；新增提交需要重新批准。"
        )
        for comment in comments:
            user = comment.get("user", {})
            if user.get("type") == "Bot" and user.get("login") == "github-actions[bot]" and comment.get("body", "").startswith(marker):
                if comment["body"] != body:
                    self.stage = "instructions_update"
                    self.client.request("PATCH", f"{self.prefix}/issues/comments/{comment['id']}", {"body": body})
                return
        self.stage = "instructions_create"
        self.client.request("POST", f"{self.prefix}/issues/{pull['number']}/comments", {"body": body})

    def run(self, event_name, event):
        try:
            return self._run(event_name, event)
        except GitHubError as error:
            # Only static stage identifiers leave the credential boundary.
            error.stage = self.stage
            raise

    def _run(self, event_name, event):
        self.stage = "repository_lookup"
        repository = self.client.request("GET", self.prefix)
        if repository.get("id") != self.policy.source_repository_id or repository.get("full_name") != self.policy.repository or repository.get("private") is not False:
            raise ValueError("Unexpected public repository identity")
        if event.get("repository", {}).get("id") != self.policy.source_repository_id:
            raise ValueError("Event belongs to another repository")
        self.stage = "pull_requests_list"
        pulls = self.client.paginate(self.prefix + "/pulls?state=open&base=main")
        pending = []
        try:
            for item in pulls:
                number = item.get("number")
                if type(number) is not int or number <= 0:
                    raise ValueError("Invalid pull request identity")
                self.stage = "pull_request_lookup"
                pull = self.client.request("GET", f"{self.prefix}/pulls/{number}")
                if pull.get("state") != "open" or pull.get("base", {}).get("ref") != "main":
                    continue
                if pull.get("base", {}).get("repo", {}).get("id") != self.policy.source_repository_id:
                    raise ValueError("Unexpected pull request base repository")
                self.stage = "status_pending"
                self.status(pull, "pending", "Checking version-bound contributor signatures")
                pending.append(pull)
            self.stage = "ledger_read"
            ledger = read_ledger(self.client, self.policy)
            self.stage = "comment_event"
            changed = event_name == "issue_comment" and apply_comment_event(self.client, self.policy, ledger, event)
            comment_pages = {}
            # GitHub concurrency can replace queued event runs. Reconcile all
            # open PRs so a missed creation event does not lose a valid signature.
            for pull in pending:
                self.stage = "comments_list"
                comments = self.client.paginate(f"{self.prefix}/issues/{pull['number']}/comments")
                comment_pages[pull["number"]] = comments
                changed = record_unseen_comments(comments, pull, self.policy, ledger) or changed
            latest = latest_signatures(ledger.records, self.policy)
            live = {}
            outcomes = []
            for pull in pending:
                try:
                    self.stage = "commit_authors"
                    authors = contributor_ids(self.client, self.policy, pull)
                except (ValueError, TypeError) as error:
                    outcomes.append((pull, "failure", str(error)))
                    continue
                missing = []
                for user_id in sorted(authors):
                    if user_id not in live:
                        record = latest.get(user_id)
                        self.stage = "signature_verify"
                        valid = record is not None and verify_live_signature(self.client, self.policy, record)
                        live[user_id] = valid
                        if record is not None and record["status"] == "active" and not valid:
                            changed = revoke(record, "live_evidence_changed") or changed
                    if not live[user_id]:
                        missing.append(user_id)
                if missing:
                    self.instructions(pull, comment_pages[pull["number"]])
                    outcomes.append((pull, "failure", "Every human contributor must sign the current CLA; see the PR instructions"))
                else:
                    outcomes.append((pull, "success", f"All human contributors signed CLA v{self.policy.cla_version}"))
            if changed:
                self.stage = "ledger_write"
                write_ledger(self.client, self.policy, ledger)
            passed = 0
            for pull, state, description in outcomes:
                self.stage = "head_recheck"
                current = self.client.request("GET", f"{self.prefix}/pulls/{pull['number']}")
                if current.get("head", {}).get("sha") != pull["head"]["sha"]:
                    state, description = "failure", "PR head changed during verification; a fresh CLA check is required"
                # Always bind the outcome to the exact head whose commits were read.
                self.stage = "status_publish"
                self.status(pull, state, description)
                passed += state == "success"
            return {"checked_pull_requests": len(outcomes), "passed": passed}
        except Exception:
            for pull in pending:
                try:
                    self.status(pull, "error", "CLA verification unavailable; no signature approval was granted")
                except (GitHubError, ValueError, TypeError, KeyError, OSError):
                    print("Could not publish the fail-closed CLA status; original failure retained", file=sys.stderr)
            raise
