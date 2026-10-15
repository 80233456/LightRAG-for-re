# Corrective EvidenceChain V2

This is an opt-in application-layer retrieval and verification strategy. The
original LightRAG adapter, NLI pipeline and previous optimization remain available.
It is not a newly trained model or a reproduction of CRAG/CoVe training results.

## Pipeline

1. Decompose a question into at most four evidence needs. For Yes/No questions,
   produce a bounded Boolean expression over at most eight source-qualified
   declarative claims. No answer labels or reference facts enter this step.
2. Fuse corpus BM25 and LightRAG graph/vector document rankings with standard
   reciprocal-rank fusion (`k=60`). Rerank relevant sliding windows with the
   existing BGE cross-encoder implementation.
3. Expand selected windows into literal parent-body spans. Use spare capacity for
   complete articles of at most 12,000 characters. Initial context is bounded at
   64,000 characters, including metadata; provenance records exact body offsets.
4. Generate a short answer and source-addressed factual rationale.
5. For Yes/No questions, verify atomic claims without showing the proposed answer
   to the fact checker. Evaluate `and`, `or`, `not` in Python using three-valued
   logic. Unknown is never treated as false. A decisive counterexample can prove
   a conjunction false without establishing every other clause.
6. The program may correct a Yes/No candidate using the verified truth expression.
   The original candidate, correction flag and decisive evidence certificate are
   all retained. Named-answer questions use the source-grounded facet verifier.
7. At most one evidence/answer repair follows unresolved evidence or refutation.
   Initial passages are preserved; the final budget is 96,000 characters and 32
   passages. Unresolved conflicts, malformed generation and invalid proof
   citations fail closed. Logical-form parsing failures use an explicit alternate
   proof audit rather than being treated as factual support.

If Boolean normalization fails or atomic evidence remains unresolved, a separate
joint proof audit can still establish the answer from valid source-addressed
facts. This is not automatic approval of uncertainty. Invalid citations and
unresolved atomic conflicts do not take that fallback. Each of at most two
verification rounds uses at most two complementary audits.

An absence-of-mention verdict is usable only for claims about report content and
only when complete coverage of the corresponding parent document is available.
Absence from a report does not disprove a real-world event or relation.

## Usage

Install the existing real/local extras, configure the private runtime environment,
and provide actual corpus and local reranker paths:

```bash
PYTHONPATH=src python scripts/ask_corrective.py "Your question" \
  --corpus /path/to/corpus.json \
  --reranker /path/to/bge-reranker-v2-m3 \
  --variant full
```

Do not commit `.env`. The large language model is DeepSeek via API; BGE embedding
and BGE reranking run locally. No local Qwen or local NLI model is required by V2.

## Evaluation Contract

`experiments/v2_experiment.py` preserves all development trials, then runs one
validation40 and one blind100 evaluation with frozen source/protocol hashes.
Previous200 test indices are excluded. Baseline, previous recovery, V2 context,
V2 verification/correction, and V2 full are evaluated on the same questions.
The initial V2 candidate is shared by exact-input caches across its ablations.
An 80% normalized-token EM target is aspirational, not an override to acceptance.
Malformed generation scores zero even for no-answer questions. Constructed verifier
controls are separate from public benchmark scores.

## Provenance And Limitations

The program copies cited passages verbatim. This guarantees passage provenance,
not that the model's atomic judgment is correct. Question-to-logic parsing and
atomic fact judgments remain model-dependent; a correct Boolean evaluator cannot
repair an incorrectly parsed question or a wrongly classified fact. Generation,
planning and fact checking share DeepSeek and can have correlated errors.
The wider context and additional reranker increase compute and API use. Exact
paired-cache timings are not independent per-variant latency measurements.

References and adaptation boundaries:

- [LightRAG](https://github.com/HKUDS/LightRAG): existing graph/vector retrieval;
  its official project also documents reranking as an optional query-stage step.
- [LlamaIndex fusion retriever](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py):
  standard reciprocal-rank fusion, not the entire framework.
- [BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3): existing pretrained
  cross-encoder relevance scoring; no new reranker training.
- [CRAG](https://arxiv.org/abs/2401.15884): corrective evidence routing; this
  implementation does not train its evaluator or use external web search.
- [RAGAS faithfulness](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/metrics/_faithfulness.py):
  atomic statement checking as a design reference, not a RAGAS score claim.
- [CoVe](https://arxiv.org/abs/2309.11495): answer-independent checking as a design
  reference, not a reproduction of the paper's reported results.
