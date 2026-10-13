"""Trusted policy loading and the exact, account-independent signing statement."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Policy:
    repository: str
    target_repository: str
    source_repository_id: int
    target_repository_id: int
    cla_version: str
    document_path: str
    document_sha256: str
    signatures_branch: str
    signatures_path: str

    @property
    def statement(self):
        return (
            f"I have read and agree to the wgpt Contributor License Agreement version {self.cla_version} "
            f"(SHA-256: {self.document_sha256}). "
            "I retain my copyright and license my contributions under the MIT License. "
            "I confirm I have the right to contribute and am not submitting confidential material. "
            "I understand my GitHub signing metadata will be public. "
            f"Please invite me to collaborate on {self.target_repository}."
        )

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Unsupported CLA policy schema")
        names = set(cls.__dataclass_fields__)
        if set(value) != names | {"schema_version"}:
            raise ValueError("Unexpected CLA policy fields")
        policy = cls(**{key: value[key] for key in names})
        if (policy.repository, policy.source_repository_id) != ("DapengFeng/wgpt-community", 1416356927):
            raise ValueError("Unexpected source repository identity")
        if (policy.target_repository, policy.target_repository_id) != ("DapengFeng/wgpt", 1415618575):
            raise ValueError("Unexpected target repository identity")
        if not isinstance(policy.cla_version, str) or not re.fullmatch(r"[1-9][0-9]*", policy.cla_version):
            raise ValueError("Invalid CLA version")
        if not isinstance(policy.document_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", policy.document_sha256):
            raise ValueError("Invalid CLA document digest")
        if (policy.document_path, policy.signatures_branch, policy.signatures_path) != (
            "CLA.md", "cla-signatures", f"signatures/v{policy.cla_version}.json"
        ):
            raise ValueError("Unexpected policy-owned document or ledger location")
        return policy


def load_policy(root: Path) -> Policy:
    root = Path(root)
    policy = Policy.from_dict(json.loads((root / "cla/policy.json").read_text(encoding="utf-8")))
    document = (root / policy.document_path).read_bytes()
    if hashlib.sha256(document).hexdigest() != policy.document_sha256:
        raise ValueError("CLA document does not match the trusted policy digest")
    return policy
