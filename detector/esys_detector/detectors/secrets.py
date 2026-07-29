"""
ESYS Secret Detection — regex-based detectors + 2 obfuscation-handling paths
(base64 decode-then-scan, adjacent string-concatenation, and a phrase-based
multi-turn-within-payload heuristic for the fragmented-token pattern).
"""

import base64
import re

# --- Core patterns (apply directly to raw text) -----------------------------

AWS_KEY_RE = re.compile(r"AKIA[0-9A-Z]{16}")
GITHUB_TOKEN_RE = re.compile(r"ghp_[A-Za-z0-9]{36}")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
DB_CONN_RE = re.compile(
    r"(?:mysql|postgres|postgresql|mongodb\+srv|mongodb)://[^\s:]+:[^\s@]+@[^\s/]+(?:/[^\s?]*)?(?:\?[^\s]*)?"
)
AZURE_KEY_RE = re.compile(r"AccountKey=([A-Za-z0-9+/]{40,}={0,2})")
SSH_KEY_RE = re.compile(r"-----BEGIN (?:OPENSSH|RSA|DSA|EC) PRIVATE KEY-----")
GCP_KEY_RE = re.compile(r"-----BEGIN PRIVATE KEY-----")

OAUTH_PATTERNS = [
    re.compile(r"SG\.[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{20,}"),
    re.compile(r"\bSK[A-Za-z0-9]{32}\b"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
]

# Base64-ish token candidates worth trying to decode
B64_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")

# String-concatenation gap: "FRAGMENT1" + "FRAGMENT2" (only useful for
# fixed-format secrets like AWS keys where we can validate the joined result)
STR_CONCAT_RE = re.compile(r'"([A-Z0-9]{6,})"\s*\+\s*"([A-Z0-9]{6,})"')

# Multi-turn-within-payload gap: the specific fragmented-token phrasing.
# Bounded quantifiers on purpose: \S+ combined with an unbounded .*? that
# must find a literal further ahead is a classic O(n^2) backtracking trap
# when "rest is:" never appears (confirmed: unbounded version hangs on
# adversarial input). Real fragments and the gap between them are always
# short, so these bounds don't affect legitimate matches.
MULTI_TURN_RE = re.compile(
    r"part of a key:\s*(\S{1,200}).{0,2000}?rest is:\s*(\S{1,200})", re.DOTALL
)


def _finding(subtype, start, end):
    return {"category": "secret", "subtype": subtype, "offset_start": start, "offset_end": end}


def detect_secrets(payload: str) -> list[dict]:
    findings = []

    for m in AWS_KEY_RE.finditer(payload):
        findings.append(_finding("aws_access_key", m.start(), m.end()))

    for m in GITHUB_TOKEN_RE.finditer(payload):
        findings.append(_finding("github_token", m.start(), m.end()))

    for m in JWT_RE.finditer(payload):
        findings.append(_finding("jwt", m.start(), m.end()))

    for m in DB_CONN_RE.finditer(payload):
        findings.append(_finding("db_connection_string", m.start(), m.end()))

    for m in AZURE_KEY_RE.finditer(payload):
        findings.append(_finding("azure_key", m.start(1), m.end(1)))

    for m in SSH_KEY_RE.finditer(payload):
        findings.append(_finding("ssh_private_key", m.start(), m.end()))

    for m in GCP_KEY_RE.finditer(payload):
        findings.append(_finding("gcp_service_account", m.start(), m.end()))

    for pattern in OAUTH_PATTERNS:
        for m in pattern.finditer(payload):
            findings.append(_finding("oauth_token", m.start(), m.end()))

    # --- Gap 1: base64-encoded secrets (decode candidate tokens, rescan) ---
    for m in B64_CANDIDATE_RE.finditer(payload):
        token = m.group(0)
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8", errors="strict")
        except Exception:
            continue
        if AWS_KEY_RE.fullmatch(decoded):
            findings.append(_finding("aws_access_key", m.start(), m.end()))

    # --- Gap 2: secret split across two adjacent quoted string literals ---
    for m in STR_CONCAT_RE.finditer(payload):
        joined = m.group(1) + m.group(2)
        if AWS_KEY_RE.fullmatch(joined):
            findings.append(_finding("aws_access_key", m.start(1), m.end(2)))

    # --- Gap 3: secret fragmented across turns within one payload ---
    mt = MULTI_TURN_RE.search(payload)
    if mt:
        joined = mt.group(1) + mt.group(2)
        if joined.startswith(("sk_live_", "sk_test_")) and len(joined) >= 24:
            findings.append(_finding("oauth_token", mt.start(1), mt.end(2)))

    return findings
