"""ESYS PII Detection — email, phone, SSN, national ID, credit card."""

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3}[\s.-]?\d{3,4}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
NATIONAL_ID_RE = re.compile(r"\b\d{9}[A-Z]{2}\d{2,3}\b")
CREDIT_CARD_RE = re.compile(r"\b\d{16}\b")


def _finding(subtype, start, end):
    return {"category": "pii", "subtype": subtype, "offset_start": start, "offset_end": end}


def detect_pii(payload: str) -> list[dict]:
    findings = []

    for m in EMAIL_RE.finditer(payload):
        findings.append(_finding("email", m.start(), m.end()))

    for m in PHONE_RE.finditer(payload):
        findings.append(_finding("phone", m.start(), m.end()))

    for m in SSN_RE.finditer(payload):
        findings.append(_finding("ssn", m.start(), m.end()))

    for m in NATIONAL_ID_RE.finditer(payload):
        findings.append(_finding("national_id", m.start(), m.end()))

    for m in CREDIT_CARD_RE.finditer(payload):
        findings.append(_finding("credit_card", m.start(), m.end()))

    return findings
