"""
Corre os detectores reais (esys_detector) sobre baseline_dataset.json e
grava predictions.json no formato que score.py espera.

Uso:
    cd detector
    python -m eval.run_predictions
    python eval/score.py eval/predictions.json
"""

import json
import os

from esys_detector.detectors.secrets import detect_secrets
from esys_detector.detectors.pii import detect_pii
from esys_detector.policy import decide

HERE = os.path.dirname(__file__)
DATASET_PATH = os.path.join(HERE, "dataset", "baseline_dataset.json")
OUT_PATH = os.path.join(HERE, "predictions.json")


def main():
    dataset = json.load(open(DATASET_PATH))
    preds = []
    for case in dataset["cases"]:
        payload = case["prompt_text"]
        findings = detect_secrets(payload) + detect_pii(payload)
        decision = decide(payload, findings)
        preds.append({
            "case_id": case["case_id"],
            "findings": findings,
            "decision": decision["action"],
        })

    with open(OUT_PATH, "w") as f:
        json.dump(preds, f, indent=2)
    print(f"Wrote {len(preds)} predictions to {OUT_PATH}")


if __name__ == "__main__":
    main()
