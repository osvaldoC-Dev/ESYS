# ESYS V1 Baseline Evaluation Dataset

320 synthetic test cases for evaluating the outbound detector + policy
pipeline against the locked go/no-go criteria. No real credentials or
real personal data — every value is generated, format-valid, and inert.

## Files

- `generate_dataset.py` — generates `baseline_dataset.json` (deterministic, seeded)
- `baseline_dataset.json` — the ground-truth corpus
- `score.py` — scoring harness, stdlib-only, CI-ready

## Category breakdown

| Category | Count | Purpose |
|---|---|---|
| Cloud/infra secrets (AWS/GCP/Azure/DB/SSH) | 110 | primary recall target, weight 5 |
| Tokens (GitHub/JWT/OAuth) | 60 | primary recall target, weight 4 |
| PII simple (email/phone/SSN/national ID) | 70 | recall target, weight 2 |
| PII structured (JSON/CSV/log) | 30 | recall target, weight 3 |
| Source code (control group) | 30 | false-positive containment, NOT a detection target |
| Clean near-miss (control group) | 30 | false-positive containment — UUIDs, hex colors, commit hashes |
| Split-fragment edge cases | 20 | documents the known V1 scope boundary |

Includes obfuscation variants (base64, string concatenation, multi-turn-within-payload)
and non-English (Portuguese) PII cases.

## Go/No-Go gates (locked, do not re-tune post-hoc)

1. **Severity-weighted recall ≥ 0.98** — weights: cloud secrets/DB/SSH = 5,
   tokens = 4, structured PII = 3, simple PII = 2. Weights are fixed before
   any tuning; changing them after seeing results defeats the point of the gate.
2. **False positive rate ≤ 0.02** on source_code + clean_near_miss control groups.
3. **Decision accuracy** — scored but not gated alone; a case can have correct
   findings and still fail if the policy engine maps them to the wrong action.

## Usage

```bash
# Generate the dataset (already done, but reproducible)
python3 generate_dataset.py

# Score your pipeline's output against it
python3 score.py your_predictions.json
```

Your pipeline needs to emit one prediction object per case:

```json
{"case_id": "baseline_0001", "findings": [{"category": "secret", "subtype": "aws_access_key", "offset_start": 40, "offset_end": 60}], "decision": "BLOCK"}
```

Run `python3 score.py` with no arguments to generate a stub predictions file
(all-ALLOW) showing the exact expected format, and to sanity-check that the
harness correctly reports NO-GO on a null detector.

## Known limitations of this dataset (be honest about these, don't discover them later)

- **320 cases, not exhaustive.** This validates the core recall/FP claim, not
  every conceivable format variant. Treat a PASS as "ready for real-traffic
  testing," not "done."
- **Synthetic secrets only.** Real-world secrets in the wild have messier
  surrounding context (mixed with unrelated logs, truncated, reformatted by
  copy-paste) than these generated examples. This is a lab benchmark, not a
  substitute for design-partner traffic.
- **Single-language focus with a Portuguese sample.** Only English + Portuguese
  are represented. Broader multilingual coverage is a real gap, not yet tested.
- **Adversarial obfuscation coverage is shallow by design.** Only 3 obfuscation
  strategies are represented (base64, string concatenation, multi-turn). The
  full adversarial suite (per earlier discussion) is a deliberate phase-2
  addition, not part of this baseline gate.
