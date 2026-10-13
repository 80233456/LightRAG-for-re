#!/usr/bin/env python3
"""RAGBench claim-support LABEL evaluation, not end-to-end answer quality.

RAGBench 'response' is a given candidate to judge, NOT an independently verified
question-answer ground truth. Baselines must classify the same pairs.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter

from evidencechain.config import settings_from_env
from evidencechain.factory import make_verifier
from evidencechain.metrics import binary_metrics
from evidencechain.schema import Evidence, split_claims


def prepare_record(row: dict, max_docs: int):
    docs = row.get("documents") or []
    if not isinstance(docs, list):
        raise ValueError("RAGBench documents expected list")
    evs = [Evidence(f"D{i+1}", str(text), f"ragbench:{row.get('id','?')}:{i}")
           for i, text in enumerate(docs[:max_docs]) if str(text).strip()]
    response = str(row.get("response") or "")
    return split_claims(response, limit=12), evs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="covidqa")
    p.add_argument("--split", default="validation", choices=("train", "validation", "test"))
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--verifier", choices=("lexical", "nli"), default="lexical")
    p.add_argument("--max-docs", type=int, default=5)
    p.add_argument("--output", default="results/ragbench_validation.json")
    args = p.parse_args()
    from datasets import load_dataset
    dataset = load_dataset("galileo-ai/ragbench", args.config, split=args.split)
    if args.limit <= 0:
        p.error("--limit must be positive")
    rows = dataset.select(range(min(args.limit, len(dataset))))
    verifier = make_verifier(settings_from_env(), args.verifier)
    gold, predictions, detail = [], [], []
    for row in rows:
        if row.get("overall_supported") is None:
            continue
        claims, evidence = prepare_record(row, args.max_docs)
        t = perf_counter()
        judged = verifier.check(claims, evidence)
        pred = bool(judged["accepted"])
        predictions.append(pred)
        gold.append(bool(row["overall_supported"]))
        detail.append({"id": row.get("id"), "gold": gold[-1], "predicted": pred,
                       "claims": claims, "verification": judged,
                       "latency_ms": round((perf_counter()-t)*1000, 2)})
    metrics = binary_metrics(gold, predictions)
    output = {"benchmark": "RAGBench-support-judgment", "config": args.config,
              "split": args.split, "limit": args.limit, "verifier": args.verifier,
              "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
              "note": "Given original response/documents. NOT RAG answer accuracy. Lexical mode = smoke only.",
              "metrics": metrics, "records": detail}
    file = Path(args.output)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("Saved", file)


if __name__ == "__main__":
    main()
