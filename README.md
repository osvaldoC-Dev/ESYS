# ESYS — AI Egress Gateway

ESYS inspects outbound requests to AI model providers (OpenAI, Anthropic,
Gemini, ...) before they're sent, and enforces a policy decision: allow,
redact, or block. It never stores the raw sensitive content it detects.

**Status:** In Development — V1

See `docs/` for the full product definition (problem, solution,
architecture, scope, metrics, roadmap).

## Repo layout

```
detector/   Python — secret + PII detection, policy engine, eval harness
proxy/      Node — minimal proxy wrapping one provider through the detector
benchmarks/ Latency measurement results
docs/       Product & engineering documentation
```

## Getting started

### Detector (Python)

```bash
cd detector
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn esys_detector.service:app --reload --port 8787
```

Run the eval harness:

```bash
cd detector
python -m eval.score
```

### Proxy (Node)

```bash
cd proxy
npm install
cp .env.example .env   # fill in OPENAI_API_KEY
npm run dev
```

## Baseline status

The V1 detector + policy pipeline has been scored against the 320-case
labeled baseline (`detector/eval/dataset/baseline_dataset.json`):

- Severity-weighted recall: **1.00** (gate: ≥ 0.98) — PASS
- False positive rate: **0.00** (gate: ≤ 0.02) — PASS
- Decision accuracy: **1.00**
- **Overall: GO**

Reproduce:

```bash
cd detector
PYTHONPATH=. python3 -m eval.run_predictions
PYTHONPATH=. python3 eval/score.py eval/predictions.json
```

## Immediate next steps

See `docs/09-next-steps.md`. With the detector gate passed, the next step
is building the minimal Node proxy against this now-passing detector, then
the latency harness.
