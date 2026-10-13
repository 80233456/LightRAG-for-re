#!/usr/bin/env python3
"""MultiHop-RAG document-corpus retrieval + QA evaluation.

CAUTION: the upstream HF configs are 'corpus' and 'MultiHopRAG'; both expose
only 'train', NOT a sealed test split. Freeze a random query holdout independently
before optimization; NEVER claim upstream split=train means model training.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from statistics import mean, median

from evidencechain.config import settings_from_env
from evidencechain.factory import make_chain
from evidencechain.metrics import answer_em, answer_f1, fact_recall
from evidencechain.pipeline import VARIANTS


def get_documents(corpus, max_corpus: int | None = None):
    docs = []
    for i, row in enumerate(corpus):
        if max_corpus is not None and i >= max_corpus:
            break
        body = str(row.get("body") or "").strip()
        if not body:
            continue
        # Tags help retrieve provenance; do NOT add reference answers or evidence_list.
        title = str(row.get("title") or "")
        date = str(row.get("published_at") or "")
        source = str(row.get("source") or "")
        content = f"Title: {title}\nPublished: {date}\nSource: {source}\nBody: {body}"
        docs.append({"id": f"multihop/{i}", "text": content})
    return docs


def gold_facts(row):
    return [str(item.get("fact") or "") for item in (row.get("evidence_list") or [])
            if isinstance(item, dict) and item.get("fact")]


async def run(args):
    from datasets import load_dataset
    if args.limit_queries <= 0:
        raise ValueError("--limit-queries must be positive")
    corpus = load_dataset("yixuantt/MultiHopRAG", "corpus", split="train")
    questions = load_dataset("yixuantt/MultiHopRAG", "MultiHopRAG", split="train")
    docs = get_documents(corpus, args.max_corpus)
    if args.portion != "pilot":
        if not args.split_file:
            raise ValueError("正式验证必须传 --split-file configs/multihop_split_indices.json")
        split = json.loads(Path(args.split_file).read_text(encoding="utf-8"))
        if split["n"] != len(questions):
            raise ValueError(f"数据集长度 {len(questions)} 与锁定划分 {split['n']} 不一致")
        indices = split[f"{args.portion}_indices"]
    else:
        indices = list(range(len(questions)))
    # Exclude null_query only if declared before testing; default retains all tasks.
    selected = [questions[i] for i in indices[:args.limit_queries]]
    settings = settings_from_env()
    chain = await make_chain(settings, args.backend, args.verifier)
    variants = VARIANTS if args.variant == "all" else (args.variant,)
    records = []
    try:
        # Real: index exactly once, then reuse same LightRAG working dir across variants.
        # Rerunning --index on unchanged docs costs time; use without --index after first run.
        if args.backend == "demo" or args.index:
            await chain.retriever.add(docs)
        for row in selected:
            query = str(row["query"])
            gold = str(row.get("answer") or "")
            facts = gold_facts(row)
            for variant in variants:
                output = await chain.ask(query, variant)
                evtexts = [item["content"] for item in output["evidence"]]
                records.append({
                    "query_sha": hashlib.sha256(query.encode()).hexdigest()[:16],
                    "question_type": row.get("question_type"),
                    "query": query,
                    "gold": gold,
                    "variant": variant,
                    "prediction": output["answer"],
                    "candidate_answer": output["candidate_answer"],
                    "abstained": output["abstained"],
                    "exact_match": answer_em(output["answer"], gold),
                    "answer_f1": answer_f1(output["answer"], gold),
                    "fact_recall_at_selected_k": fact_recall(evtexts, facts),
                    "latency_ms": output["latency_ms"],
                    "retrieval": output["retrieval"],
                    "verification": output["verification"],
                    "evidence": output["evidence"],
                })
    finally:
        await chain.retriever.close()
    summary = {}
    for variant in variants:
        arr = [r for r in records if r["variant"] == variant]
        fact_scores = [r["fact_recall_at_selected_k"] for r in arr if r["fact_recall_at_selected_k"] is not None]
        summary[variant] = {
            "n": len(arr),
            "em": mean(r["exact_match"] for r in arr),
            "f1": mean(r["answer_f1"] for r in arr),
            "fact_recall": mean(fact_scores) if fact_scores else None,
            "coverage": 1 - mean(float(r["abstained"]) for r in arr),
            "mean_latency_ms_exploratory": mean(r["latency_ms"] for r in arr),
            "mean_retrieval_calls": mean(r["retrieval"]["calls"] for r in arr),
        }
    out = {
        "benchmark": "MultiHop-RAG", "query_selection": args.portion, "split_file": args.split_file,
        "backend": args.backend, "verifier": args.verifier,
        "limit_queries": args.limit_queries, "corpus_size": len(docs),
        "dataset_fingerprints": {"corpus": getattr(corpus, "_fingerprint", None),
                                 "questions": getattr(questions, "_fingerprint", None)},
        "max_corpus_debug": args.max_corpus,
        "note": "MultiHop has no official test split. pilot first-N is non-official; test uses precommitted seeded indices. Do not tune on test.",
        "summary": summary, "records": records,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Saved", path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=("demo", "lightrag"), default="lightrag")
    p.add_argument("--variant", choices=(*VARIANTS, "all"), default="all")
    p.add_argument("--verifier", choices=("lexical", "nli"), default="nli")
    p.add_argument("--limit-queries", type=int, default=20)
    p.add_argument("--portion", choices=("pilot", "dev", "validation", "test"), default="pilot")
    p.add_argument("--split-file", default=None, help="Frozen indices made BEFORE tuning")
    p.add_argument("--max-corpus", type=int, default=None,
                   help="DEBUG ONLY; truncated corpus invalidates official comparison")
    p.add_argument("--index", action="store_true", help="Build full corpus index before querying")
    p.add_argument("--output", default="results/multihop_pilot.json")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
