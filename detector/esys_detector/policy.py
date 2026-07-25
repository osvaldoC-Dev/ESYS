"""
Policy engine. Rule (derived from the labeled dataset, not guessed):
  - any secret finding                          -> BLOCK
  - national_id, ssn, credit_card                -> BLOCK
  - email, phone found in structured data
    (JSON/CSV-shaped payload)                    -> BLOCK
  - email, phone found in plain text/log         -> REDACT
  - no findings                                  -> ALLOW
"""

import re

STRUCTURED_HINT_RE = re.compile(r'[{\[].*".*":.*[}\]]|,\w.*,\w.*,', re.DOTALL)


def _looks_structured(payload: str) -> bool:
    """Heuristic: payload contains a JSON object/array or a comma-delimited
    row (CSV-like), as opposed to plain prose or a log line."""
    return bool(STRUCTURED_HINT_RE.search(payload))


def decide(payload: str, findings: list[dict]) -> dict:
    if not findings:
        return {"action": "ALLOW", "findings": findings}

    block_subtypes = {"national_id", "ssn", "credit_card"}
    has_secret = any(f["category"] == "secret" for f in findings)
    has_block_pii = any(f["subtype"] in block_subtypes for f in findings)

    if has_secret or has_block_pii:
        return {"action": "BLOCK", "findings": findings}

    # Remaining case: only email/phone findings
    if _looks_structured(payload):
        return {"action": "BLOCK", "findings": findings}

    return {"action": "REDACT", "findings": findings}
