"""
Policy engine. Rule (derived from the labeled dataset, not guessed):
  - any secret finding                          -> BLOCK
  - national_id, ssn, credit_card                -> BLOCK
  - email, phone found in structured data
    (JSON/CSV-shaped payload)                    -> BLOCK
  - email, phone found in plain text/log         -> REDACT
  - no findings                                  -> ALLOW
"""

import secrets as _secrets_module


def _looks_structured(payload: str) -> bool:
    """Heuristic: payload contains a JSON object/array or a comma-delimited
    row (CSV-like), as opposed to plain prose or a log line.

    Uses plain substring/count checks instead of a chained-wildcard regex
    on purpose: a pattern like `[{\\[].*".*":.*[}\\]]` looks harmless but is
    catastrophically slow (multi-second to unbounded hangs) on adversarial
    input such as `'{"key":' * 30000` — three sequential unbounded `.*`
    groups create combinatorial backtracking when the expected closing
    bracket never appears. Plain string ops here are O(n), no exceptions.
    """
    has_bracket = "{" in payload or "[" in payload
    has_json_kv = '":' in payload
    if has_bracket and has_json_kv:
        return True

    for line in payload.split("\n"):
        if line.count(",") >= 2:
            return True

    return False


def _tokenize(payload: str, findings: list[dict]) -> tuple[str, dict]:
    """Replace each finding's span with a unique reversible token, instead
    of a static [REDACTED:subtype] placeholder.

    Why this exists: a static placeholder loses information the model
    might have needed ("reply to this email" breaks once the email is
    gone). A reversible token lets the model see *something* in that
    position — enough to keep the conversation coherent — while the real
    value never leaves this process. The mapping is returned so the
    caller (the proxy) can substitute the real value back into the
    provider's response before it reaches the user, and then discard the
    mapping. It is never written to disk or logged.

    The same original value always gets the same token within one call —
    e.g. if an email appears twice in the same payload, both occurrences
    get the same ESYS_TOK_xxxx, not two different ones. Without this, the
    model would see what looks like two unrelated values where there was
    actually one, breaking exactly the coherence tokenization exists to
    preserve (e.g. "my email is X... confirm X is correct" needs both X's
    to look identical to the model).

    Processes findings back-to-front so replacing one span never shifts
    the offsets of the findings still to be processed.
    """
    ordered = sorted(findings, key=lambda f: f["offset_start"], reverse=True)
    tokenized = payload
    token_map: dict[str, str] = {}
    value_to_token: dict[str, str] = {}
    for f in ordered:
        original_value = payload[f["offset_start"]:f["offset_end"]]
        token = value_to_token.get(original_value)
        if token is None:
            token = f"ESYS_TOK_{_secrets_module.token_hex(4)}"
            value_to_token[original_value] = token
            token_map[token] = original_value
        tokenized = tokenized[: f["offset_start"]] + token + tokenized[f["offset_end"] :]
    return tokenized, token_map


def decide(payload: str, findings: list[dict]) -> dict:
    if not findings:
        return {"action": "ALLOW", "findings": findings, "redacted_payload": None, "token_map": None}
    block_subtypes = {"national_id", "ssn", "credit_card", "cpf_br", "national_id_za", "nin_ng", "iban_eu"}
    has_secret = any(f["category"] == "secret" for f in findings)
    has_block_pii = any(f["subtype"] in block_subtypes for f in findings)
    has_prompt_injection = any(f["category"] == "prompt_injection" for f in findings)
    if has_secret or has_block_pii or has_prompt_injection:
        return {"action": "BLOCK", "findings": findings, "redacted_payload": None, "token_map": None}

    if _looks_structured(payload):
        return {"action": "BLOCK", "findings": findings, "redacted_payload": None, "token_map": None}

    tokenized_payload, token_map = _tokenize(payload, findings)
    return {
        "action": "REDACT",
        "findings": findings,
        "redacted_payload": tokenized_payload,
        "token_map": token_map,
    }