# Scope

## What ESYS V1 does

Sits between applications and AI model providers (OpenAI so far; Anthropic
and Gemini planned), inspects the complete outbound request payload before
it's sent, and enforces: allow / redact / block. Never stores the raw
sensitive content it detects.

Detects:
- **Secrets**: AWS/GCP/Azure keys, GitHub tokens, JWTs, OAuth tokens, DB
  connection strings, SSH keys — including obfuscated variants (base64,
  string-concatenation, multi-turn fragmentation).
- **PII, across 4 regions**: emails, phone numbers, credit cards, US SSN,
  Angola national ID, Brazil CPF/CNPJ (checksum-validated), South Africa
  national ID (checksum-validated), Nigeria NIN, EU IBAN
  (checksum-validated) — including structured formats (JSON, CSV, logs).

Handles both request shapes a real client can send:
- **Synchronous** (single JSON response).
- **Streaming** (Server-Sent Events) — the outbound prompt is inspected in
  full either way; only how the *response* is relayed differs.

Redaction is **reversible tokenization**, not static placeholders: a
redacted value becomes a unique `ESYS_TOK_xxxxxxxx` token, and the real
value is substituted back into the model's response before it reaches the
user — the model never sees the real value, but the conversation stays
coherent (e.g. "reply to this email" still works). The same value repeated
in one payload always gets the same token. This only applies to the
non-streaming response path today (see Non-goals below).

Every BLOCK is logged locally (`esys-review`) with a reviewable audit
trail — a false positive can be inspected and marked reviewed, it's never
silently lost.

## Non-goals (V1 intentionally does not)

- Inspect model responses for *new* findings (only the outbound request
  is inspected).
- Detect prompt injection.
- Store prompt contents outside the local BLOCK audit log.
- Maintain cross-request memory.
- Detect proprietary source code.
- **Reverse tokens in streaming responses** — a token can be split across
  two SSE chunks, which needs a small buffering strategy that hasn't been
  built yet. Streaming responses are relayed as-is; a raw `ESYS_TOK_xxxx`
  may appear in a streamed reply today. Documented, not hidden.

These are explicit scope boundaries, not gaps to apologize for — except
the last one, which is a known rough edge, tracked for a later pass.
