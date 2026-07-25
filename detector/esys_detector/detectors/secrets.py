"""
Secret detection: AWS/GCP/Azure keys, GitHub tokens, JWTs, OAuth tokens,
DB connection strings, SSH keys.

Each detector function should return a list of Finding objects — never
the raw matched secret itself (V1 non-goal: don't store prompt contents).
"""

from dataclasses import dataclass


@dataclass
class Finding:
    detector: str        # e.g. "aws_access_key"
    category: str        # "secret"
    start: int            # char offset in the payload
    end: int
    severity: str          # "high" / "medium" / "low"
    # Deliberately no `value` field — never persist the raw match.


def detect(payload: str) -> list[Finding]:
    """
    Run all secret detectors against a raw text payload and return findings.

    TODO: implement each pattern as its own function (aws_keys, gcp_keys,
    azure_keys, github_tokens, jwts, oauth_tokens, db_conn_strings, ssh_keys)
    and aggregate here. Keep each detector independently testable against
    the eval dataset.
    """
    findings: list[Finding] = []
    # TODO: findings += _detect_aws_keys(payload)
    # TODO: findings += _detect_github_tokens(payload)
    # TODO: findings += _detect_jwts(payload)
    # ...
    return findings
