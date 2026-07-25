"""
Scoring harness: runs the detector against the labeled 320-case dataset
and reports recall, false positive rate, and p95 added latency.

Usage:
    python -m eval.score --dataset eval/dataset/cases.jsonl

Targets (see docs/metrics.md):
    Recall              >= 98%
    False Positive Rate <= 2%
    Added latency (p95) <  30ms
"""

import argparse
import json
import time
from pathlib import Path

from esys_detector.detectors import pii, secrets


def load_cases(path: Path) -> list[dict]:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run(dataset_path: Path) -> None:
    cases = load_cases(dataset_path)

    tp = fp = fn = tn = 0
    latencies_ms: list[float] = []

    for case in cases:
        payload = case["payload"]
        should_flag = bool(case["should_flag"])  # ground truth label

        start = time.perf_counter()
        findings = secrets.detect(payload) + pii.detect(payload)
        latencies_ms.append((time.perf_counter() - start) * 1000)

        flagged = len(findings) > 0
        if flagged and should_flag:
            tp += 1
        elif flagged and not should_flag:
            fp += 1
        elif not flagged and should_flag:
            fn += 1
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    fp_rate = fp / (fp + tn) if (fp + tn) else float("nan")
    latencies_ms.sort()
    p95 = latencies_ms[int(len(latencies_ms) * 0.95) - 1] if latencies_ms else float("nan")

    print(f"Cases:               {len(cases)}")
    print(f"Recall:              {recall:.2%}  (target >= 98%)")
    print(f"False Positive Rate: {fp_rate:.2%}  (target <= 2%)")
    print(f"Latency p95:         {p95:.2f}ms  (target < 30ms)")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "dataset" / "cases.jsonl",
    )
    args = parser.parse_args()
    run(args.dataset)
