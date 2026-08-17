"""
Prompt injection detection — deliberately narrow, regex/keyword-based.

HONEST LIMITATION (read before trusting this in production):
This only catches "classic" / well-known injection phrasings from the
2022-2024 era (goal hijacking, DAN-style jailbreaks, developer-mode
unlocks, system-prompt extraction). Current research (2026) is clear
that frontier models already resist most of these through training —
and that the attacks that actually matter today largely evade regex
entirely:
  - Indirect injection: malicious instructions hidden inside documents,
    web pages, or RAG-retrieved content the model processes, not in
    the user's own text. This detector never sees that content in a
    way that would let it distinguish attack from legitimate content.
  - Multi-turn steering: manipulation spread across several messages,
    none of which look suspicious in isolation. Reported bypass rates
    against published defenses exceed 90% in the literature.
Proper coverage of either needs a trained classifier (e.g. Meta's
Prompt Guard, ProtectAI's deberta-v3 prompt-injection model), not
pattern matching — that's a real architecture change (inference
latency budget, model hosting), not a regex addition, and hasn't been
justified by real user evidence yet (see docs: Engineering Hypotheses
/ "prove one surface before expanding").

This detector exists as one thin layer of defense-in-depth, not a
claim of prompt-injection coverage. Ship it as exactly that.

All patterns use BOUNDED gaps (.{0,N}) between anchor phrases, never
unbounded (.*) — lesson learned from the ReDoS bugs found earlier in
this project (see docs: Metrics / Robustness section).
"""

import re

IGNORE_OVERRIDE_RE = re.compile(
    r"\b(?:ignore|disregard)\b.{0,30}\b(?:previous|all|prior|above)\b.{0,30}\b(?:instructions?|rules?|prompts?)\b",
    re.IGNORECASE,
)

DAN_JAILBREAK_RE = re.compile(
    r"\bdo\s+anything\s+now\b|\bDAN\b.{0,30}\b(?:mode|jailbreak)\b",
    re.IGNORECASE,
)

DEVELOPER_MODE_RE = re.compile(
    r"\b(?:enable|activate|unlock)\b.{0,20}\b(?:developer|debug|admin)\s+mode\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT_EXTRACTION_RE = re.compile(
    r"\b(?:reveal|show|print|repeat|output)\b.{0,20}\b(?:system\s+prompt|initial\s+prompt|instructions\s+above)\b",
    re.IGNORECASE,
)

PATTERNS = {
    "goal_hijack": IGNORE_OVERRIDE_RE,
    "dan_jailbreak": DAN_JAILBREAK_RE,
    "developer_mode_unlock": DEVELOPER_MODE_RE,
    "system_prompt_extraction": SYSTEM_PROMPT_EXTRACTION_RE,
}


def _finding(subtype, start, end):
    return {"category": "prompt_injection", "subtype": subtype, "offset_start": start, "offset_end": end}


def detect_prompt_injection(payload: str) -> list[dict]:
    findings = []
    for subtype, pattern in PATTERNS.items():
        for m in pattern.finditer(payload):
            findings.append(_finding(subtype, m.start(), m.end()))
    return findings
