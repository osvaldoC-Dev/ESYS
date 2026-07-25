"""
Policy engine: turns a list of findings into a single decision.

Decision is one of: "allow", "redact", "block".
"""

from dataclasses import dataclass
from enum import Enum

from esys_detector.detectors.secrets import Finding


class Decision(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class PolicyResult:
    decision: Decision
    findings: list[Finding]
    redacted_payload: str | None = None  # only set when decision == REDACT


def evaluate(payload: str, findings: list[Finding]) -> PolicyResult:
    """
    TODO: define the default V1 policy. Suggested starting point:
      - any "high" severity secret finding -> BLOCK
      - PII findings only -> REDACT (mask the matched spans)
      - no findings -> ALLOW
    This should be overridable later by policy packs (planned, not V1).
    """
    if not findings:
        return PolicyResult(decision=Decision.ALLOW, findings=[])

    # TODO: implement real severity-based logic
    return PolicyResult(decision=Decision.BLOCK, findings=findings)
