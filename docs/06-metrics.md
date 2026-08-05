# Metrics

| Metric               | Target  | Result   | Status |
|-----------------------|---------|----------|--------|
| Recall (severity-weighted) | >= 98%  | 100%     | PASS   |
| False Positive Rate   | <= 2%   | 0%       | PASS   |
| Added Latency (p95)   | < 30ms  | 3.72ms   | PASS   |

The whole product bet rested on hitting these three numbers together
against the 320-case labeled eval dataset. **They were hit.** The
architecture is technically validated — this is no longer the open
question it started as.

Recall and false-positive rate cover secrets, PII across all 4 regions
(Angola, Brazil, South Africa/Nigeria, US, EU), and obfuscated variants
(base64, string-concatenation, multi-turn fragmentation).

Latency is the *delta* the ESYS layer adds — proxy + detector round trip —
isolated from a mock provider response, not mixed with the AI provider's
own (variable, uncontrollable) latency.

Reproduce:
```bash
cd detector
python -m eval.run_predictions
python eval/score.py eval/predictions.json
```
```bash
node benchmarks/latency_harness.js --n 200 --payload clean
```

## Robustness (found via adversarial testing, not part of the original gate)

The original 3 metrics say nothing about behavior under malformed,
adversarial, or oversized input — a separate round of testing surfaced 6
real bugs, all fixed:

- 3 ReDoS (regex denial-of-service) bugs that caused multi-second to
  unbounded hangs on adversarial text (email detection, structured-payload
  detection, multi-turn secret fragmentation).
- A token-coherence bug (same value getting different tokens on repeat).
- An information-disclosure bug (malformed JSON leaked server file paths
  via a stack trace).
- An audit-log fragility bug (one corrupted log line crashed the whole
  review CLI).

None of these would have shown up in the recall/FP/latency gate above —
that gate tests *correctness* on well-formed input, not *resilience*
against malformed or hostile input. Both matter; they're different tests.
