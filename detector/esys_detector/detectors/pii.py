"""
ESYS PII Detection.

Coverage by region (this is the "Africa + Brazil + EU + US" expansion —
not just US/EU like most competitors in this space):

  Global    : email, phone, credit_card
  Angola    : national_id           (existing BI format)
  Brazil    : cpf, cnpj             (with real checksum validation)
  S. Africa : national_id_za        (with Luhn checksum validation)
  Nigeria   : nin                   (context-gated — no public checksum exists)
  USA       : ssn
  EU        : iban                  (with mod-97 checksum validation)

Where a real checksum algorithm exists (CPF, CNPJ, ZA ID, IBAN), we
validate it — this is what keeps false positives near zero even though
these are just "digits in a specific shape" that could otherwise appear
by coincidence in unrelated numbers.
"""

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3}[\s.-]?\d{3,4}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
NATIONAL_ID_RE = re.compile(r"\b\d{9}[A-Z]{2}\d{2,3}\b")  # Angola BI format
CREDIT_CARD_RE = re.compile(r"\b\d{16}\b")

CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CNPJ_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
ZA_ID_RE = re.compile(r"\b\d{13}\b")
NIN_CONTEXT_RE = re.compile(r"(?:NIN|National Identification Number)\D{0,10}(\d{11})", re.IGNORECASE)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){1,6}\s?[A-Z0-9]{0,4}\b")


def _finding(subtype, start, end):
    return {"category": "pii", "subtype": subtype, "offset_start": start, "offset_end": end}


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _cpf_valid(cpf: str) -> bool:
    d = _digits(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):
        total = sum(int(d[j]) * (i + 1 - j) for j in range(i))
        check = (total * 10) % 11
        check = 0 if check == 10 else check
        if check != int(d[i]):
            return False
    return True


def _cnpj_valid(cnpj: str) -> bool:
    d = _digits(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for i, weights in ((12, weights1), (13, weights2)):
        total = sum(int(d[j]) * weights[j] for j in range(i))
        check = 11 - (total % 11)
        check = 0 if check >= 10 else check
        if check != int(d[i]):
            return False
    return True


def _za_id_valid(number: str) -> bool:
    if len(number) != 13 or not number.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_valid(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if not (15 <= len(iban) <= 34):
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97 == 1


def detect_pii(payload: str) -> list[dict]:
    findings = []

    if "@" in payload:
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

    for m in CPF_RE.finditer(payload):
        if _cpf_valid(m.group(0)):
            findings.append(_finding("cpf_br", m.start(), m.end()))

    for m in CNPJ_RE.finditer(payload):
        if _cnpj_valid(m.group(0)):
            findings.append(_finding("cnpj_br", m.start(), m.end()))

    for m in ZA_ID_RE.finditer(payload):
        if _za_id_valid(m.group(0)):
            findings.append(_finding("national_id_za", m.start(), m.end()))

    for m in NIN_CONTEXT_RE.finditer(payload):
        findings.append(_finding("nin_ng", m.start(1), m.end(1)))

    for m in IBAN_RE.finditer(payload):
        if _iban_valid(m.group(0)):
            findings.append(_finding("iban_eu", m.start(), m.end()))

    return findings
