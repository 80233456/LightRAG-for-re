"""Audit the archived 2026-10-14 model records without calling any model.

This audits HISTORICAL outputs, not the current algorithm's accuracy.
Example:
python scripts/offline_audit_archive.py evidencechain_experiment_20261014.zip --output results/offline_audit.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import mean
from zipfile import ZipFile

from evidencechain.adaptive import AdaptiveController
from evidencechain.schema import overlap

ROOT = "evidencechain_experiment/results"


def _load_rows(archive: ZipFile, path: str) -> list[dict]:
    text = archive.read(f"{ROOT}/{path}").decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _metrics(rows: list[dict], answerable_key: str) -> dict:
    if not rows:
        raise ValueError("No records for this group")
    def answerable(row: dict) -> bool:
        return (row.get("question_type") != "null_query" if answerable_key == "question_type"
                else bool(row[answerable_key]))
    valid = [row for row in rows if answerable(row)]
    answered = [row for row in rows if bool(row["output"]["answer"])]
    return {
        "n": len(rows),
        "recorded_em": round(mean(float(row["em"]) for row in rows), 6),
        "answerable_n": len(valid),
        "recorded_answerable_em": round(mean(float(row["em"]) for row in valid), 6) if valid else None,
        "recorded_answer_coverage": round(len(answered) / len(rows), 6),
        "recorded_mean_retrieval_calls": round(mean(row["output"]["retrieval"]["calls"]
                                                    for row in rows), 6),
    }


def audit_archive(path: str | Path) -> dict:
    controller = AdaptiveController()
    with ZipFile(path) as archive:
        onsite = _load_rows(archive, "onsite/records.jsonl")
        multihop = _load_rows(archive, "multihop_dev20/records.jsonl")
    onsite_test = [row for row in onsite if row["split"] == "test"]
    variants = ("baseline", "adaptive", "verify", "full")
    onsite_summary = {
        v: _metrics([row for row in onsite_test if row["variant"] == v], "answerable")
        for v in variants
    }
    multihop_summary = {
        v: _metrics([row for row in multihop if row["variant"] == v], "question_type")
        for v in variants
    }
    # WARNING: only old mix@8 evidence is available. No new retrieval, NLI
    # inference, or answer generation takes place in this diagnostic.
    baseline_rows = [row for row in multihop if row["variant"] == "baseline"]
    triggers = []
    for row in baseline_rows:
        question = row.get("query") or row["output"]["question"]
        ev = row["output"]["evidence"]
        risk = controller.prior_risk(question)
        coverage = overlap(question, " ".join(x["content"] for x in ev))
        triggers.append({
            "index": row["index"], "question_type": row.get("question_type"),
            "risk": round(risk, 4), "first_pass_word_overlap": round(coverage, 4),
            "would_request_expansion": bool(risk >= controller.risk_threshold
                                            or coverage < controller.coverage_threshold)
        })
    if len(onsite_test) != 180 or len(multihop) != 80:
        raise ValueError("Expected old onsite test 45x4 and MultiHop 20x4 records")
    if len(baseline_rows) != 20 or len({x["index"] for x in baseline_rows}) != 20:
        raise ValueError("Expected 20 unique historical MultiHop baseline questions")
    return {
        "kind": "historical_diagnostic_only",
        "source": "2026-10-14 original experiment archive",
        "warning": "Old scores only. No new model accuracy or retrieval cost measured.",
        "onsite_old_test": onsite_summary,
        "multihop_old_dev20": multihop_summary,
        "current_controller_trigger_probe_on_old_baseline_evidence": {
            "n": len(triggers),
            "triggered": sum(x["would_request_expansion"] for x in triggers),
            "not_triggered": sum(not x["would_request_expansion"] for x in triggers),
            "rows": triggers,
            "warning": "Predicted triggers only; not rerun retrieval, answers or token costs."
        }
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    data = audit_archive(args.archive)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
