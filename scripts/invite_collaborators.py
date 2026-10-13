#!/usr/bin/env python3
"""Invite contributors only after a live CLA and owner approval of their PR."""

import argparse
import base64
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cla.github import GitHubClient, GitHubError
from cla.policy import load_policy
from cla.signatures import latest_signatures, read_ledger, verify_live_signature

MAX_INVITATIONS = 10
MAX_DAILY_INVITATIONS = 40
MAX_LEDGER_BYTES = 1_000_000
STATUSES = {
    "attempted", "invited", "accepted", "existing_access", "existing_invitation",
    "unresolved", "expired_or_declined", "withdrawn", "cancelled",
}


def positive_id(value):
    return type(value) is int and value > 0


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Invalid invitation timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class MaintainerApproval:
    """Bind human approval to one applicant PR revision and signing request."""

    pull_request: int
    review_id: int
    reviewer_id: int
    head_sha: str
    submitted_at: str

    @classmethod
    def from_dict(cls, value):
        if (
            not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__)
            or any(not positive_id(value.get(key)) for key in ("pull_request", "review_id", "reviewer_id"))
            or not isinstance(value.get("head_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", value["head_sha"])
        ):
            raise ValueError("Invalid maintainer approval evidence")
        timestamp(value.get("submitted_at"))
        return cls(**value)


class ApprovalGate:
    """Only the verified public repository owner can authorize private access."""

    def __init__(self, public, policy, owner_id):
        self.public, self.policy, self.owner_id = public, policy, owner_id

    def read(self, record):
        path = f"/repos/{self.policy.repository}/pulls/{record['pull_request']}"
        try:
            pull = self.public.request("GET", path)
        except GitHubError as error:
            if error.status == 404:
                return None
            raise
        if not self.eligible_pull(pull, record):
            return None
        head = pull["head"]["sha"]
        latest, seen = None, set()
        # GitHub returns reviews chronologically. Comments do not replace a decision;
        # dismissals and change requests do, without reviving an older approval.
        for review in self.public.paginate(path + "/reviews"):
            if (
                not isinstance(review, dict) or not positive_id(review.get("id"))
                or review["id"] in seen or not isinstance(review.get("user"), dict)
                or not positive_id(review["user"].get("id"))
            ):
                raise ValueError("Invalid pull request review evidence")
            seen.add(review["id"])
            user = review["user"]
            if user["id"] != self.owner_id or user.get("type") != "User":
                continue
            if review.get("pull_request_url") != "https://api.github.com" + path:
                raise ValueError("Approval belongs to a different pull request")
            state = review.get("state")
            if state in {"COMMENTED", "PENDING"}:
                continue
            if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
                raise ValueError("Unknown maintainer review state")
            latest = review
        if (
            latest is None or latest["state"] != "APPROVED"
            or latest.get("commit_id") != head
            or timestamp(latest.get("submitted_at")) <= timestamp(record["created_at"])
        ):
            return None
        # A head change or PR closure during pagination must invalidate the read.
        current = self.public.request("GET", path)
        if not self.eligible_pull(current, record) or current["head"]["sha"] != head:
            return None
        return MaintainerApproval.from_dict({
            "pull_request": record["pull_request"], "review_id": latest["id"],
            "reviewer_id": self.owner_id, "head_sha": head,
            "submitted_at": latest["submitted_at"],
        })

    def eligible_pull(self, pull, record):
        if (
            not isinstance(pull, dict) or not positive_id(pull.get("number"))
            or any(not isinstance(pull.get(key), dict) for key in ("user", "base", "head"))
            or not isinstance(pull["base"].get("repo"), dict)
            or not positive_id(pull["user"].get("id"))
            or not positive_id(pull["base"]["repo"].get("id"))
            or not isinstance(pull["base"].get("ref"), str) or not pull["base"]["ref"]
            or pull.get("state") not in {"open", "closed"}
            or type(pull.get("draft")) is not bool
            or not isinstance(pull["head"].get("sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", pull["head"]["sha"])
        ):
            raise ValueError("Invalid approval pull request response")
        return (
            pull.get("number") == record["pull_request"]
            and pull.get("state") == "open" and pull.get("draft") is False
            and pull.get("user", {}).get("id") == record["user_id"]
            and record["user_id"] != self.owner_id
            and pull.get("base", {}).get("ref") == "main"
            and pull.get("base", {}).get("repo", {}).get("id") == self.policy.source_repository_id
        )


class InvitationJournal:
    """Persist send intent before PUT; ambiguous attempts cannot be replayed."""

    def __init__(self, public, policy):
        self.public = public
        self.policy = policy
        self.path = f"/repos/{policy.repository}/contents/invitations/v{policy.cla_version}.json"
        self.sha = None
        self.attempts = []

    def load(self):
        try:
            file = self.public.request(
                "GET", f"{self.path}?ref={self.policy.signatures_branch}",
            )
        except GitHubError as error:
            if error.status != 404:
                raise
            return
        if (
            not isinstance(file, dict) or file.get("encoding") != "base64"
            or file.get("type") != "file"
            or file.get("path") != self.path.split("/contents/", 1)[1]
        ):
            raise ValueError("Invalid invitation journal response")
        raw = base64.b64decode(file["content"].replace("\n", ""), validate=True)
        if len(raw) > MAX_LEDGER_BYTES:
            raise ValueError("Invitation journal size limit reached")
        expected = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False,
        ).hexdigest()
        if file.get("sha") != expected:
            raise ValueError("Invitation journal content does not match its revision")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"schema_version", "attempts"} or data.get("schema_version") != 1 or not isinstance(data.get("attempts"), list):
            raise ValueError("Unsupported invitation journal")
        keys = set()
        for item in data["attempts"]:
            if (
                not isinstance(item, dict)
                or not positive_id(item.get("user_id"))
                or not positive_id(item.get("comment_id"))
                or item.get("status") not in STATUSES
                or item.get("document_sha256") != self.policy.document_sha256
                or item.get("cla_version") != self.policy.cla_version
                or not isinstance(item.get("attempted_at"), str)
                or type(item.get("request_intent")) is not bool
                or ("invitation_id" in item and not positive_id(item["invitation_id"]))
            ):
                raise ValueError("Invalid invitation journal record")
            key = (item["user_id"], item["comment_id"])
            if key in keys:
                raise ValueError("Duplicate invitation journal record")
            keys.add(key)
            timestamp(item["attempted_at"])
            # Old journals remain recovery evidence, never a substitute for live approval.
            if "approval" in item:
                MaintainerApproval.from_dict(item["approval"])
        if not isinstance(file.get("sha"), str) or len(file["sha"]) != 40:
            raise ValueError("Missing invitation journal revision")
        self.attempts, self.sha = data["attempts"], file["sha"]

    def save(self):
        raw = json.dumps({"schema_version": 1, "attempts": self.attempts}, indent=2)
        content = (raw + "\n").encode()
        if len(content) > MAX_LEDGER_BYTES:
            raise ValueError("Invitation journal size limit reached")
        body = {
            "message": "chore: record collaborator invitation state",
            "branch": self.policy.signatures_branch,
            "content": base64.b64encode(content).decode(),
        }
        if self.sha:
            body["sha"] = self.sha
        saved = self.public.request("PUT", self.path, body)
        entry = saved.get("content", {}) if isinstance(saved, dict) else {}
        expected = hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content, usedforsecurity=False,
        ).hexdigest()
        sha = entry.get("sha")
        if sha != expected or entry.get("path") != self.path.split("/contents/", 1)[1]:
            raise ValueError("Invitation journal commit was not acknowledged")
        self.sha = sha

    def find(self, record):
        return next((item for item in self.attempts if (
            item["user_id"] == record["user_id"]
            and item["comment_id"] == record["comment_id"]
        )), None)

    def begin(self, record, status, *, approval=None):
        if status == "attempted" and not isinstance(approval, MaintainerApproval):
            raise ValueError("Invitation intent requires maintainer approval evidence")
        item = {
            "user_id": record["user_id"], "comment_id": record["comment_id"],
            "cla_version": self.policy.cla_version,
            "document_sha256": self.policy.document_sha256,
            "attempted_at": utc_now(), "status": status,
            "request_intent": status == "attempted",
        }
        if approval is not None:
            item["approval"] = asdict(approval)
        self.attempts.append(item)
        self.save()
        return item

    def update(self, item, status, **fields):
        item.update(status=status, **fields)
        self.save()


class InvitationReconciler:
    """Keep public signature evidence separate from the invitation credential."""

    def __init__(self, public, private, policy, *, apply=False):
        self.public, self.private, self.policy = public, private, policy
        self.apply = apply
        self.journal = InvitationJournal(public, policy)
        self.events = []
        self.approval_gate = None

    def event(self, user_id, status):
        self.events.append({"user_id": user_id, "status": status})

    def repositories(self):
        for client, name, identity, private in (
            (self.public, self.policy.repository, self.policy.source_repository_id, False),
            (self.private, self.policy.target_repository, self.policy.target_repository_id, True),
        ):
            value = client.request("GET", f"/repos/{name}")
            if (
                not isinstance(value, dict) or value.get("id") != identity
                or value.get("full_name") != name or value.get("private") is not private
            ):
                raise ValueError("Repository identity or visibility changed")
            if private and value.get("owner", {}).get("type") != "User":
                raise ValueError("Invitation policy requires a personal repository")
            if not private:
                owner = value.get("owner", {})
                if owner.get("type") != "User" or not positive_id(owner.get("id")):
                    raise ValueError("Approval policy requires a human repository owner")
                self.approval_gate = ApprovalGate(self.public, self.policy, owner["id"])
        branch = self.public.request(
            "GET", f"/repos/{self.policy.repository}/branches/{self.policy.signatures_branch}",
        )
        if not isinstance(branch, dict) or branch.get("name") != self.policy.signatures_branch:
            raise ValueError("Signature branch is not initialized")

    def inventory(self):
        prefix = f"/repos/{self.policy.target_repository}"
        collaborators = self.private.paginate(f"{prefix}/collaborators")
        invitations = self.private.paginate(f"{prefix}/invitations")
        users, pending = set(), {}
        for user in collaborators:
            if not isinstance(user, dict) or not positive_id(user.get("id")):
                raise ValueError("Invalid collaborator inventory")
            users.add(user["id"])
        for invite in invitations:
            if (
                not isinstance(invite, dict) or not positive_id(invite.get("id"))
                or not isinstance(invite.get("invitee"), dict)
                or not positive_id(invite["invitee"].get("id"))
            ):
                raise ValueError("Invalid invitation inventory")
            user_id = invite["invitee"]["id"]
            if user_id in pending:
                raise ValueError("Ambiguous pending invitations")
            pending[user_id] = invite
        return users, pending

    def user(self, user_id):
        user = self.public.request("GET", f"/user/{user_id}")
        login = user.get("login") if isinstance(user, dict) else None
        if (
            not isinstance(user, dict) or user.get("id") != user_id
            or user.get("type") != "User" or not isinstance(login, str)
            or not login or len(login) > 39
            or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in login)
        ):
            raise ValueError("GitHub account identity changed")
        return login

    def signature_current(self, record):
        # A still-valid old comment cannot authorize a newer request to join.
        latest = latest_signatures(read_ledger(self.public, self.policy).records, self.policy)
        return latest.get(record["user_id"]) == record and verify_live_signature(self.public, self.policy, record)

    def cancel_withdrawn(self, valid, approvals, pending):
        # Cancellation applies only to an exact invitation created by this worker.
        for item in self.journal.attempts:
            record = valid.get(item["user_id"])
            eligible = (
                record is not None and record["comment_id"] == item["comment_id"]
                and approvals.get(item["user_id"]) is not None
            )
            if eligible or item["status"] not in {"invited", "attempted", "unresolved"}:
                continue
            invitation = pending.get(item["user_id"])
            owned = invitation and invitation["id"] == item.get("invitation_id")
            if not self.apply:
                self.event(item["user_id"], "would_cancel" if owned else "withdrawn")
                continue
            if owned:
                self.private.request(
                    "DELETE", f"/repos/{self.policy.target_repository}/invitations/{invitation['id']}",
                )
                self.journal.update(item, "cancelled")
                del pending[item["user_id"]]
            else:
                self.journal.update(item, "withdrawn")
            self.event(item["user_id"], item["status"])

    def run(self):
        self.repositories()
        snapshot = read_ledger(self.public, self.policy)
        latest = latest_signatures(snapshot.records, self.policy)
        # Complete evidence reads before any invitation side effects.
        approvals = {
            user_id: self.approval_gate.read(record) if record["status"] == "active" else None
            for user_id, record in latest.items()
        }
        valid = {
            user_id: record for user_id, record in latest.items()
            if verify_live_signature(self.public, self.policy, record)
        }
        users, pending = self.inventory()
        self.journal.load()
        if latest_signatures(read_ledger(self.public, self.policy).records, self.policy) != latest:
            raise ValueError("Signature ledger changed during reconciliation; no invitation changes applied")
        self.cancel_withdrawn(valid, approvals, pending)
        sent = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = sum(
            item["request_intent"] and timestamp(item["attempted_at"]) >= cutoff
            for item in self.journal.attempts
        )
        for user_id, record in sorted(valid.items()):
            item = self.journal.find(record)
            if approvals[user_id] is None and user_id not in users:
                self.event(user_id, "human_approval_required")
                continue
            if user_id in users or user_id in pending:
                status = "existing_access" if user_id in users else "existing_invitation"
                if self.apply:
                    if item is None:
                        self.journal.begin(record, status)
                    elif item["status"] in {"attempted", "invited", "unresolved"} and user_id in users:
                        self.journal.update(item, "accepted")
                self.event(user_id, status)
                continue
            if item:
                # A declined, expired or ambiguous request needs a fresh explicit signature.
                if self.apply and item["status"] == "invited":
                    self.journal.update(item, "expired_or_declined")
                self.event(user_id, "prior_attempt_requires_new_request")
                continue
            if sent >= MAX_INVITATIONS or recent >= MAX_DAILY_INVITATIONS:
                self.event(user_id, "deferred_run_limit")
                continue
            login = self.user(user_id)
            if not self.apply:
                self.event(user_id, "would_invite")
                sent += 1
                recent += 1
                continue
            # Recheck both independent gates before recording irreversible intent.
            if not self.signature_current(record):
                self.event(user_id, "signature_no_longer_valid")
                continue
            approval = self.approval_gate.read(record)
            if approval is None:
                self.event(user_id, "human_approval_required")
                continue
            item = self.journal.begin(record, "attempted", approval=approval)
            sent += 1
            recent += 1
            # Persisting intent is a network write. Revalidate afterwards as well;
            # a withdrawal during that write must not authorize an invitation.
            if (
                not self.signature_current(record)
                or self.approval_gate.read(record) != approval
            ):
                self.journal.update(item, "withdrawn")
                self.event(user_id, "authorization_changed_before_invitation")
                continue
            invitation = self.private.request(
                "PUT", f"/repos/{self.policy.target_repository}/collaborators/{login}",
            )
            if invitation is None:
                self.journal.update(item, "existing_access")
                self.event(user_id, "existing_access")
                continue
            if (
                not isinstance(invitation, dict) or not positive_id(invitation.get("id"))
                or invitation.get("invitee", {}).get("id") != user_id
                or invitation.get("repository", {}).get("id") != self.policy.target_repository_id
            ):
                self.journal.update(item, "unresolved")
                raise ValueError("Invitation response identity mismatch; no automatic retry")
            self.journal.update(item, "invited", invitation_id=invitation["id"])
            pending[user_id] = invitation
            self.event(user_id, "invited")
        return self.events


def require_trusted_workflow(environment):
    if (
        environment.get("GITHUB_REPOSITORY_ID") != "1416356927"
        or environment.get("GITHUB_REPOSITORY") != "DapengFeng/wgpt-community"
        or environment.get("GITHUB_REF") != "refs/heads/main"
        or environment.get("GITHUB_EVENT_NAME") not in {"schedule", "workflow_dispatch"}
    ):
        raise ValueError("Invitation writes require the trusted main workflow")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Send verified invitations; otherwise read only")
    args = parser.parse_args()
    if args.apply:
        require_trusted_workflow(os.environ)
    policy = load_policy(Path(__file__).resolve().parents[1])
    public_token = os.environ.get("GITHUB_TOKEN")
    private_token = os.environ.get("WGPT_COLLABORATOR_TOKEN")
    if not public_token or not private_token:
        raise ValueError("Configure the restricted invitation environment credentials")
    result = InvitationReconciler(
        GitHubClient(public_token), GitHubClient(private_token), policy, apply=args.apply,
    ).run()
    print(json.dumps({"apply": args.apply, "results": result}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (GitHubError, ValueError) as error:
        # GitHubError is deliberately sanitized by the shared transport.
        raise SystemExit(str(error)) from None
