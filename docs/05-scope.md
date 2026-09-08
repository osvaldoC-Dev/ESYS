# Scope

## What ESYS V1 does

Sits between applications and AI model providers (OpenAI and Anthropic,
with full format translation including streaming; Gemini planned),
inspects the complete outbound request payload before it's sent, and
enforces: allow / redact / block. Never stores the raw sensitive content
it detects.

Detects:
- **Secrets**: AWS/GCP/Azure keys, GitHub tokens, JWTs, OAuth tokens, DB
  connection strings, SSH keys — including obfuscated variants (base64,
  string-concatenation, multi-turn fragmentation).
- **PII, across 4 regions**: emails, phone numbers, credit cards, US SSN,
  Angola national ID (context-gated — no public checksum exists), Brazil
  CPF/CNPJ (checksum-validated), South Africa national ID
  (checksum-validated), Nigeria NIN (context-gated), EU IBAN
  (checksum-validated) — including structured formats (JSON, CSV, logs).
- **Prompt injection**: goal hijacking, jailbreak attempts (DAN-style),
  system prompt extraction — pattern-based detection of classic attacks.
  Documented limitation: this does not cover indirect injection (hidden
  in documents the model processes) or multi-turn manipulation, which
  need a different approach (ML classifiers, not regex) — see Metrics.

Handles both request shapes a real client can send:
- **Synchronous** (single JSON response).
- **Streaming** (Server-Sent Events) — the outbound prompt is inspected in
  full either way.

Redaction is **reversible tokenization**, not static placeholders: a
redacted value becomes a unique `ESYS_TOK_xxxxxxxx` token, and the real
value is substituted back into the model's response before it reaches the
user — the model never sees the real value, but the conversation stays
coherent (e.g. "reply to this email" still works). The same value repeated
in one payload always gets the same token. This works for both response
shapes: token reversal is chunk-safe across SSE boundaries (verified with
441 adversarial chunk-split combinations — see Current Status), not just
the non-streaming path.

**Response inspection (non-streaming only)**: the model's reply is also
scanned — for secrets/PII the model itself produced (a hallucinated key,
leaked context) — before token reversal happens, so the user's own
legitimately-returned data is never mistaken for a new leak. Streaming
responses are not yet covered by this (see Non-goals).

Every BLOCK is logged locally (`esys-review`) with a reviewable audit
trail — a false positive can be inspected and marked reviewed, it's never
silently lost. The log lives outside cloud-synced folders by default
(`~/.esys/`), with an automatic warning if it ever ends up inside one
anyway.

## Non-goals (V1 intentionally does not)

- **Inspect streaming responses for new findings** — only the
  non-streaming response path is scanned for content the model produced
  on its own. Streaming responses still get token reversal (the user's
  own data comes back correctly), just not this additional scan. The
  reason: you can't "un-send" SSE chunks already streamed to the client,
  so this needs a genuinely different design, not just more code — see
  Metrics/Engineering Hypotheses for why this isn't a quick fix.
- Detect indirect prompt injection (hidden in documents the model
  processes) or multi-turn manipulation — only classic single-turn
  patterns are covered (see above).
- Store prompt contents outside the local BLOCK audit log.
- Maintain cross-request memory.
- Detect proprietary source code.

These are explicit scope boundaries, not gaps to apologize for.