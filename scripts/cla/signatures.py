"""Versioned signature evidence, revocation and compare-and-swap persistence."""

import base64
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from .github import GitHubError


def human_account(value):
    return (
        isinstance(value, dict) and value.get("type") == "User"
        and type(value.get("id")) is int and value["id"] > 0
        and isinstance(value.get("login"), str)
        and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value["login"]) is not None
    )


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("Invalid signature timestamp")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def validate_record(record):
    if not isinstance(record, dict):
        raise TypeError("Invalid signature record")
    required = {"user_id", "login", "comment_id", "pull_request", "created_at", "updated_at", "cla_version", "document_sha256", "status"}
    optional = {"revoked_at", "revocation_reason"}
    if not required <= record.keys() or record.keys() - required - optional:
        raise ValueError("Invalid signature record fields")
    for key in ("user_id", "comment_id", "pull_request"):
        if type(record[key]) is not int or record[key] <= 0:
            raise ValueError("Invalid signature identifier")
    if not human_account({"id": record["user_id"], "login": record["login"], "type": "User"}):
        raise ValueError("Invalid signature login")
    _timestamp(record["created_at"])
    _timestamp(record["updated_at"])
    if record["updated_at"] != record["created_at"]:
        raise ValueError("A signature must originate from an unedited comment")
    if not isinstance(record["cla_version"], str) or not re.fullmatch(r"[1-9][0-9]*", record["cla_version"]):
        raise ValueError("Invalid signature version")
    if not isinstance(record["document_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["document_sha256"]):
        raise ValueError("Invalid signature document digest")
    if record["status"] == "revoked":
        _timestamp(record.get("revoked_at"))
        if record.get("revocation_reason") not in {"comment_edited", "comment_deleted", "live_evidence_changed"}:
            raise ValueError("Invalid signature revocation reason")
    elif record["status"] != "active" or optional & record.keys():
        raise ValueError("Invalid signature status")
    return record


@dataclass
class LedgerSnapshot:
    records: list
    sha: str | None


def _ledger_path(policy):
    return f"/repos/{policy.repository}/contents/{policy.signatures_path}"


def read_ledger(client, policy):
    try:
        value = client.request("GET", _ledger_path(policy) + "?ref=" + quote(policy.signatures_branch, safe=""))
    except GitHubError as error:
        if error.status == 404:
            return LedgerSnapshot([], None)
        raise
    if not isinstance(value, dict) or value.get("type") != "file" or value.get("encoding") != "base64":
        raise ValueError("Expected a regular signature ledger")
    sha = value.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("Missing signature ledger revision")
    content = base64.b64decode("".join(value["content"].split()), validate=True)
    if len(content) > 1024 * 1024:
        raise ValueError("Signature ledger exceeds limit")
    data = json.loads(content)
    if not isinstance(data, dict) or set(data) != {"schema_version", "signatures"} or data["schema_version"] != 1:
        raise ValueError("Invalid signature ledger schema")
    records = data["signatures"]
    if not isinstance(records, list) or len(records) > 5000:
        raise ValueError("Invalid signature ledger size")
    seen = set()
    for record in records:
        validate_record(record)
        if record["comment_id"] in seen:
            raise ValueError("Duplicate signing comment")
        seen.add(record["comment_id"])
    return LedgerSnapshot(records, sha)


def write_ledger(client, policy, snapshot):
    for record in snapshot.records:
        validate_record(record)
    data = json.dumps({"schema_version": 1, "signatures": snapshot.records}, indent=2, ensure_ascii=True) + "\n"
    body = {
        "message": f"Record CLA v{policy.cla_version} signature evidence",
        "branch": policy.signatures_branch,
        "content": base64.b64encode(data.encode()).decode(),
    }
    if snapshot.sha is not None:
        body["sha"] = snapshot.sha
    # A conflict must fail the gate. Never overwrite an independently changed ledger.
    result = client.request("PUT", _ledger_path(policy), body)
    payload = data.encode()
    expected_sha = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload, usedforsecurity=False).hexdigest()
    if (
        not isinstance(result, dict)
        or result.get("content", {}).get("sha") != expected_sha
        or result.get("content", {}).get("path") != policy.signatures_path
    ):
        raise ValueError("GitHub did not confirm the exact signature ledger write")


def latest_signatures(records, policy):
    latest = {}
    for record in records:
        if record["cla_version"] != policy.cla_version or record["document_sha256"] != policy.document_sha256:
            continue
        key = record["user_id"]
        if key not in latest or (record["created_at"], record["comment_id"]) > (latest[key]["created_at"], latest[key]["comment_id"]):
            latest[key] = record
    # Keep revoked latest entries; selecting an older active record would undo withdrawal.
    return latest


def _same_signature(comment, pull, policy, record):
    return (
        human_account(comment.get("user")) and human_account(pull.get("user"))
        and comment["user"]["id"] == record["user_id"] == pull["user"]["id"]
        and comment.get("id") == record["comment_id"]
        and comment.get("body") == policy.statement
        and comment.get("created_at") == record["created_at"]
        and comment.get("updated_at") == record["updated_at"]
        and comment.get("issue_url") == f"https://api.github.com/repos/{policy.repository}/issues/{record['pull_request']}"
        and pull.get("number") == record["pull_request"]
        and pull.get("base", {}).get("repo", {}).get("id") == policy.source_repository_id
    )


def verify_live_signature(client, policy, record):
    validate_record(record)
    if record["status"] != "active" or record["cla_version"] != policy.cla_version or record["document_sha256"] != policy.document_sha256:
        return False
    try:
        comment = client.request("GET", f"/repos/{policy.repository}/issues/comments/{record['comment_id']}")
        pull = client.request("GET", f"/repos/{policy.repository}/pulls/{record['pull_request']}")
    except GitHubError as error:
        if error.status == 404:
            return False
        raise
    if not isinstance(comment, dict) or not isinstance(pull, dict):
        raise TypeError("Invalid signature evidence response")
    return bool(_same_signature(comment, pull, policy, record))


def record_comment(comment, pull, policy):
    if not human_account(comment.get("user")) or not human_account(pull.get("user")):
        return None
    record = {
        "user_id": comment["user"]["id"], "login": comment["user"]["login"],
        "comment_id": comment.get("id"), "pull_request": pull.get("number"),
        "created_at": comment.get("created_at"), "updated_at": comment.get("updated_at"),
        "cla_version": policy.cla_version, "document_sha256": policy.document_sha256,
        "status": "active",
    }
    if comment.get("updated_at") != comment.get("created_at") or not _same_signature(comment, pull, policy, record):
        return None
    validate_record(record)
    return record


def revoke(record, reason, now=None):
    if record["status"] == "revoked":
        return False
    record.update(
        status="revoked", revocation_reason=reason,
        revoked_at=now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return True


def apply_comment_event(client, policy, snapshot, event):
    action = event.get("action")
    comment_id = event.get("comment", {}).get("id")
    if type(comment_id) is not int or comment_id <= 0 or not event.get("issue", {}).get("pull_request"):
        return False
    if action in {"edited", "deleted"}:
        for record in snapshot.records:
            if record["comment_id"] == comment_id:
                return revoke(record, "comment_" + action)
        return False
    if action != "created" or any(record["comment_id"] == comment_id for record in snapshot.records):
        return False
    number = event["issue"].get("number")
    if type(number) is not int or number <= 0:
        raise ValueError("Invalid signing pull request number")
    try:
        comment = client.request("GET", f"/repos/{policy.repository}/issues/comments/{comment_id}")
        pull = client.request("GET", f"/repos/{policy.repository}/pulls/{number}")
    except GitHubError as error:
        if error.status == 404:
            return False
        raise
    record = record_comment(comment, pull, policy)
    if record is None:
        return False
    snapshot.records.append(copy.deepcopy(record))
    return True


def record_unseen_comments(comments, pull, policy, snapshot):
    """Recover missed creation events without reviving known revoked comments."""
    known = {record["comment_id"] for record in snapshot.records}
    changed = False
    for comment in comments:
        if comment.get("id") in known:
            continue
        record = record_comment(comment, pull, policy)
        if record is not None:
            snapshot.records.append(record)
            known.add(record["comment_id"])
            changed = True
    return changed
