"""
PII detection: emails, phone numbers, SSNs, national IDs, credit cards.

Must handle structured formats (JSON, CSV, log lines) and non-English
content, per V1 scope.
"""

from esys_detector.detectors.secrets import Finding


def detect(payload: str) -> list[Finding]:
    """
    Run all PII detectors against a raw text payload and return findings.

    TODO: implement each pattern/model as its own function (emails, phones,
    ssns, national_ids, credit_cards) and aggregate here. Consider a
    structure-aware pass (parse JSON/CSV first, fall back to raw regex scan)
    since V1 must handle both plain text and structured payloads.
    """
    findings: list[Finding] = []
    # TODO: findings += _detect_emails(payload)
    # TODO: findings += _detect_phone_numbers(payload)
    # TODO: findings += _detect_credit_cards(payload)
    # ...
    return findings
