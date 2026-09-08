# Current Status

ESYS has moved past "will this even work" into "it works, now what."

## What's proven

- Core detector validated against a 320-case labeled dataset: 100%
  recall, 0% false positives, across secrets and PII in 4 regions
  (Angola, Brazil, South Africa/Nigeria, US, EU).
- Minimal proxy wired end-to-end: a request with a secret gets blocked
  before it reaches a provider; a clean request passes through.
- Added latency from the whole inspection layer: 3.72ms at p95 (target
  was <30ms).
- **Reversible tokenization**: redacted PII becomes a real-but-fake token
  the model can process; the true value is substituted back into the
  response before the user sees it. Tested end-to-end with a token round
  trip (model sees `ESYS_TOK_xxxx`, user sees the real value back).
- **Streaming support**: the proxy correctly relays Server-Sent Events
  chunk-by-chunk instead of buffering the whole response — required for
  compatibility with how most real AI apps actually call these APIs.
- **Streaming + redaction together**: token reversal is safe across SSE
  chunk boundaries — a `ESYS_TOK_xxxx` token is never released to the
  client split across two network chunks. Verified with 441 adversarial
  chunk-split combinations (single event cut byte-by-byte, and multi-event
  streams cut at 6 different network chunk sizes) plus a real end-to-end
  run through the live proxy on both the OpenAI and Anthropic streaming
  paths: zero leaked tokens, output byte-identical to the non-streaming
  detokenization result.
- **Audit trail**: every BLOCK is logged locally with a reviewable CLI
  (`esys-review`) — a false positive is never silently lost.
- **`esys-watch`**: published to PyPI (`pip install esys-watch`), MIT
  licensed, zero external dependencies for the CLI path. Includes a
  `--demo` mode for a zero-friction first try (no file needed).
- **Prompt injection detection**: pattern-based coverage of classic
  attacks (goal hijacking, DAN-style jailbreaks, system prompt
  extraction) — documented as not covering indirect/multi-turn attacks,
  which need a different approach (see Engineering Hypotheses).
- **Response inspection (non-streaming)**: the model's reply is scanned
  for secrets/PII it produced on its own — before token reversal, so the
  user's own legitimately-returned data is never mistaken for a new
  leak (verified with a dedicated test proving the ordering is correct).
- 12+ real robustness bugs found via adversarial testing and fixed,
  across two rounds — see Metrics for the full list.

## What's still open, honestly

- Everything above was validated against a synthetic dataset built for
  this purpose, and adversarial inputs *we* constructed. It hasn't been
  tested against real, messy, unpredictable traffic from someone else yet
  — that's the next real test, not this one.
- Streaming responses don't get the new response-inspection scan yet —
  only non-streaming does (see Scope: Non-goals for why this is a
  genuinely different problem, not just more code).
- This is still a one-person project. Every gap above is a sequencing
  choice, not an oversight: prove correctness and resilience before
  distribution, UI, or anything that depends on the core being
  trustworthy.

## Bottom line

The technical foundation is no longer a question mark, and it's been
stress-tested beyond the original gate, not just validated once and left
alone. What's left is real-world validation (a first external tester is
lined up), and building outward — the free layer that gets this in front
of users beyond the founder's own machine.