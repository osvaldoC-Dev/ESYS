"""
ESYS V1 Baseline Scoring Harness
---------------------------------
Consumes:
  1. baseline_dataset.json (ground truth)
  2. your pipeline's predictions in the same shape (see PREDICTIONS_SCHEMA below)

Computes, per the locked go/no-go criteria:
  - Severity-weighted recall (fixed weights, not re-tunable post-hoc)
  - False positive rate (on clean_near_miss + source_code control groups)
  - Decision accuracy (independent of finding-level correctness)

PREDICTIONS_SCHEMA (what your pipeline should output per case):
{
  "case_id": "baseline_0001",
  "findings": [ {"category": "...", "subtype": "...", "offset_start": N, "offset_end": N} ],
  "decision": "BLOCK" | "REDACT" | "ALLOW"
}

Usage:
  python3 score.py predictions.json

This is deliberately dependency-free (stdlib only) so it can drop into
any CI pipeline without setup friction.
"""

import json
import sys
from collections import defaultdict

IOU_THRESHOLD = 0.5  # minimum overlap to count a predicted finding as matching a ground-truth finding

def overlap(a_start, a_end, b_start, b_end):
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0

def load_json(path):
    with open(path) as f:
        return json.load(f)

def score(dataset_path, predictions_path):
    dataset = load_json(dataset_path)
    preds = load_json(predictions_path)
    weights = dataset["severity_weights"]
    cases_by_id = {c["case_id"]: c for c in dataset["cases"]}
    preds_by_id = {p["case_id"]: p for p in preds}

    missing = set(cases_by_id) - set(preds_by_id)
    if missing:
        print(f"WARNING: {len(missing)} cases have no prediction (treated as ALLOW / no findings): {list(missing)[:5]}...")

    # --- Severity-weighted recall (findings-level, excludes control groups) ---
    weighted_tp = 0.0
    weighted_total = 0.0
    per_subtype_recall = defaultdict(lambda: {"tp": 0, "total": 0})

    # --- False positive tracking (control groups only) ---
    fp_count = 0
    fp_total = 0
    fp_cases = []

    # --- Decision accuracy (all cases) ---
    decision_correct = 0
    decision_total = 0
    decision_confusion = defaultdict(lambda: defaultdict(int))
    decision_errors = []

    for case_id, case in cases_by_id.items():
        pred = preds_by_id.get(case_id, {"findings": [], "decision": "ALLOW"})
        gt_findings = case["expected_findings"]
        pred_findings = pred.get("findings", [])
        w = weights.get(case["subtype"], 0)

        # Recall scoring — only for cases with actual sensitive content
        if gt_findings:
            for gtf in gt_findings:
                weighted_total += w
                per_subtype_recall[case["subtype"]]["total"] += 1
                matched = any(
                    pf.get("subtype") == gtf["subtype"] and
                    overlap(pf["offset_start"], pf["offset_end"], gtf["offset_start"], gtf["offset_end"]) >= IOU_THRESHOLD
                    for pf in pred_findings
                )
                if matched:
                    weighted_tp += w
                    per_subtype_recall[case["subtype"]]["tp"] += 1

        # False positive scoring — only for control groups (source_code, clean_near_miss)
        if case["category"] in ("source_code", "clean_near_miss"):
            fp_total += 1
            if len(pred_findings) > 0:
                fp_count += 1
                fp_cases.append(case_id)

        # Decision accuracy — all cases
        decision_total += 1
        actual_decision = pred.get("decision", "ALLOW")
        expected_decision = case["expected_decision"]
        decision_confusion[expected_decision][actual_decision] += 1
        if actual_decision == expected_decision:
            decision_correct += 1
        else:
            decision_errors.append((case_id, expected_decision, actual_decision))

    weighted_recall = weighted_tp / weighted_total if weighted_total > 0 else float("nan")
    fp_rate = fp_count / fp_total if fp_total > 0 else float("nan")
    decision_accuracy = decision_correct / decision_total if decision_total > 0 else float("nan")

    print("=" * 60)
    print("ESYS V1 BASELINE SCORING REPORT")
    print("=" * 60)
    print(f"\nSeverity-weighted recall: {weighted_recall:.4f}  (gate: >= 0.98)")
    print(f"  {'PASS' if weighted_recall >= 0.98 else 'FAIL'}")
    print(f"\nFalse positive rate (control groups): {fp_rate:.4f}  (gate: <= 0.02)")
    print(f"  {'PASS' if fp_rate <= 0.02 else 'FAIL'}")
    print(f"\nDecision accuracy (all cases): {decision_accuracy:.4f}")

    print(f"\n--- Recall by subtype ---")
    for subtype, d in sorted(per_subtype_recall.items(), key=lambda x: -weights.get(x[0], 0)):
        r = d["tp"] / d["total"] if d["total"] else float("nan")
        flag = " <-- below gate" if r < 0.98 else ""
        print(f"  {subtype:25s} weight={weights.get(subtype,0)}  recall={r:.3f} ({d['tp']}/{d['total']}){flag}")

    if fp_cases:
        print(f"\n--- False positive cases ({len(fp_cases)}) ---")
        for cid in fp_cases[:15]:
            print(f"  {cid}")
        if len(fp_cases) > 15:
            print(f"  ... and {len(fp_cases) - 15} more")

    if decision_errors:
        print(f"\n--- Decision errors ({len(decision_errors)} of {decision_total}) ---")
        for cid, exp, act in decision_errors[:15]:
            print(f"  {cid}: expected={exp} got={act}")
        if len(decision_errors) > 15:
            print(f"  ... and {len(decision_errors) - 15} more")

    print(f"\n--- Decision confusion matrix ---")
    all_decisions = sorted(set(decision_confusion.keys()) | {k for v in decision_confusion.values() for k in v})
    header = "expected\\got".ljust(12) + "".join(d.ljust(10) for d in all_decisions)
    print(header)
    for exp in all_decisions:
        row = exp.ljust(12) + "".join(str(decision_confusion[exp].get(got, 0)).ljust(10) for got in all_decisions)
        print(row)

    overall_pass = weighted_recall >= 0.98 and fp_rate <= 0.02
    print(f"\n{'=' * 60}")
    print(f"OVERALL GO/NO-GO: {'GO' if overall_pass else 'NO-GO'}")
    print(f"{'=' * 60}")
    return overall_pass


if __name__ == "__main__":
    import os
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset", "baseline_dataset.json")
    if len(sys.argv) < 2:
        print("Usage: python3 score.py <predictions.json>")
        print("\nGenerating a stub predictions file (all-ALLOW, no findings) to show expected format...")
        dataset = load_json(dataset_path)
        stub = [{"case_id": c["case_id"], "findings": [], "decision": "ALLOW"} for c in dataset["cases"]]
        with open("predictions_stub.json", "w") as f:
            json.dump(stub, f, indent=2)
        print("Wrote predictions_stub.json (320 cases, all ALLOW / no findings)")
        print("Run: python3 score.py predictions_stub.json   to see a baseline (expected: fails badly)")
        sys.exit(0)
    score(dataset_path, sys.argv[1])
