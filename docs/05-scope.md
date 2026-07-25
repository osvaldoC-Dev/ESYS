# Scope

## What ESYS V1 does

Sits between applications and AI model providers (OpenAI, Anthropic,
Gemini, ...), inspects the complete outbound request payload before it's
sent, and enforces: allow / redact / block. Never stores the raw sensitive
content it detects.

Detects:
- **Secrets**: AWS/GCP/Azure keys, GitHub tokens, JWTs, OAuth tokens, DB
  connection strings, SSH keys.
- **PII**: emails, phone numbers, SSNs, national IDs, credit cards —
  including structured formats (JSON, CSV, logs) and non-English content.

## Non-goals (V1 intentionally does not)

- Inspect model responses.
- Detect prompt injection.
- Store prompt contents.
- Maintain cross-request memory.
- Detect proprietary source code.

These are explicit scope boundaries, not gaps to apologize for.
