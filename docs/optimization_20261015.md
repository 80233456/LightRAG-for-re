# Opt-in joint evidence verification

The existing `make_chain` and NLI pipeline remain unchanged. The new
`make_grounded_chain` uses the same LightRAG retriever and DeepSeek generator,
but verifies the proposed answer jointly against retrieved passages. It checks
literal source quotations after semantic adjudication. This is a pragmatic
inference strategy, not a trained model, formal proof, or Self-RAG reproduction.

```bash
PYTHONPATH=src python scripts/ask_grounded.py "Your question" --variant full
```

Runtime configuration uses the existing private environment: `LLM_PROVIDER`,
`LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LIGHTRAG_WORKDIR`, and embedding
settings. Do not commit `.env` or put credentials in command-line arguments.

## Invariants

- Initial generation retains the baseline prompt and original top-eight context.
- Evidence is then assigned unique identifiers for source-checked verification.
- A supported judgment requires one to six facts with real quotations from the
  actual visible context. Quotes alone do not establish semantic correctness.
- Recovery is allowed only for missing answers or insufficient evidence, never
  explicit refutation, conflict, invalid output, or malformed generation.
- At most two question-only decomposition queries are issued. Initial evidence
  is preserved; additional results are interleaved up to twelve final passages.
- At most two generations use genuinely different context; no repeated sampling
  until an answer happens to pass. Provider transport retries are separate.
- `baseline`, `adaptive`, `verify`, and `full` expose inference ablations.
- The answer is never rewritten by the verifier. Accepted rationale contains
  only reconstructed, source-quoted facts, not the generator's unverified claims.

## Evaluation

`experiments/optimization.py` freezes new validation32/test100 selections from
the existing MultiHop-RAG split. Previously evaluated test100 questions are
excluded. It compares baseline, unchanged NLI full, joint verification only,
recovery only, and the combined optimization. Reference answers are used only
after inference for scoring. Exact-input paired caches reduce variance and cost;
their timings must not be reported as independent per-variant latency.

`experiments/negative_controls.py` runs real-model semantic and adversarial
checks. These are constructed regression cases, not additional benchmark scores.

## Limitations

Generation and verification share DeepSeek, so their errors can be correlated.
Verification requires extra API calls and is not guaranteed to improve EM.
Insufficient first-pass evidence may remain insufficient after bounded recovery.
This answer-centric verifier does not certify every sentence in a long response;
do not relabel its QA scores as RAGBench adherence performance.
