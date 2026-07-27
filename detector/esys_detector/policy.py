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


def _redact(payload: str, findings: list[dict]) -> str:
    """Replace each finding's span with a [REDACTED:subtype] placeholder."""
    ordered = sorted(findings, key=lambda f: f["offset_start"], reverse=True)
    redacted = payload
    for f in ordered:
        placeholder = f"[REDACTED:{f['subtype']}]"
        redacted = redacted[: f["offset_start"]] + placeholder + redacted[f["offset_end"] :]
    return redacted


def decide(payload: str, findings: list[dict]) -> dict:
    if not findings:
        return {"action": "ALLOW", "findings": findings, "redacted_payload": None}

    block_subtypes = {
        "national_id", "ssn", "credit_card",
        "cpf_br", "national_id_za", "nin_ng", "iban_eu",
    }
    has_secret = any(f["category"] == "secret" for f in findings)
    has_block_pii = any(f["subtype"] in block_subtypes for f in findings)

    if has_secret or has_block_pii:
        return {"action": "BLOCK", "findings": findings, "redacted_payload": None}

    if _looks_structured(payload):
        return {"action": "BLOCK", "findings": findings, "redacted_payload": None}

    return {"action": "REDACT", "findings": findings, "redacted_payload": _redact(payload, findings)}
