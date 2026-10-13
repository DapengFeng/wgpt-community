"""Run the CLA status gate using trusted main-branch policy and GitHub metadata."""

import json
import os
import subprocess
import sys
from pathlib import Path

from cla.gate import SignatureGate
from cla.github import GitHubClient
from cla.policy import load_policy


def main():
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    if os.environ.get("GITHUB_REPOSITORY") != policy.repository:
        raise ValueError("This workflow must run in the configured public repository")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("CLA policy must be executed from the protected main branch")
    name = os.environ.get("GITHUB_EVENT_NAME")
    if name not in {"issue_comment", "pull_request_target", "push", "schedule", "workflow_dispatch"}:
        raise ValueError("Unsupported CLA trigger")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    client = GitHubClient(os.environ.get("GITHUB_TOKEN", ""))
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    print(json.dumps(SignatureGate(client, policy, document_revision=revision).run(name, event)))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - redact unexpected failures at the credential boundary.
        # API failures never print request bodies, tokens or untrusted PR content.
        print(f"CLA gate failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1)
