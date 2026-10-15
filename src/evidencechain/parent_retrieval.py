"""Corpus-only hybrid retrieval, rank fusion, reranking and parent-span expansion.

RRF follows the standard k=60 formulation also used by LlamaIndex. BM25 and
cross-encoder scoring use existing libraries, not a new retrieval engine.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re

from .schema import Evidence

STOP = set('a an the and or of to in on at by for from with as is are was were be been '
           'has have had did does do which what who whom whose how that this these those '
           'according reported report article articles both its their it there'.split())


def retrieval_tokens(text):
    return [word for word in re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text.casefold()) if word not in STOP]


@dataclass(frozen=True)
class ParentDocument:
    document_id: str
    header: str
    body: str


def corpus_documents(records):
    documents = []
    for index, row in enumerate(records):
        document_id = str(row.get('id') or f'multihop/{index}')
        header = '\n'.join(f'{label}: {row.get(field) or ""}' for label, field in
                           [('Title', 'title'), ('Author', 'author'), ('Published', 'published_at'), ('Source', 'source'), ('URL', 'url')])
        documents.append(ParentDocument(document_id, header, str(row.get('body', row.get('text', '')))))
    return documents


def reciprocal_rank_fusion(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, document_id in enumerate(dict.fromkeys(ranking)):
            scores[document_id] = scores.get(document_id, 0.0)+1/(k+rank)
    return sorted(scores, key=lambda document_id: (-scores[document_id], document_id))


class CrossEncoderReranker:
    def __init__(self, model_path, device='cuda', batch_size=8):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_path, device=device, max_length=512)
        self.batch_size = batch_size

    async def score(self, query, texts):
        if not texts:
            return []
        values = await asyncio.to_thread(self.model.predict, [(query, text) for text in texts],
                                        batch_size=self.batch_size, show_progress_bar=False)
        return [float(value) for value in values]


class ParentCorpusIndex:
    def __init__(self, documents, window_chars=1100, stride=850):
        from rank_bm25 import BM25Okapi
        if not documents or stride <= 0 or window_chars < stride:
            raise ValueError('Need nonempty documents and overlapping positive windows')
        self.documents = {doc.document_id: doc for doc in documents}
        if len(self.documents) != len(documents):
            raise ValueError('Duplicate parent document ids')
        self.ids = list(self.documents)
        self.doc_bm25 = BM25Okapi([retrieval_tokens(doc.header+'\n'+doc.header+'\n'+doc.body) or ['__empty__']
                                   for doc in documents])
        self.windows = []
        for doc in documents:
            for start in range(0, len(doc.body), stride):
                end = min(len(doc.body), start+window_chars)
                self.windows.append((doc.document_id, start, end))
                if end == len(doc.body):
                    break
        if not self.windows:
            raise ValueError('Corpus has no text')
        self.window_bm25 = BM25Okapi([retrieval_tokens(self.window_text(i)) or ['__empty__']
                                      for i in range(len(self.windows))])

    def window_text(self, index):
        document_id, start, end = self.windows[index]
        doc = self.documents[document_id]
        return doc.header+'\nBody:\n'+doc.body[start:end]

    def rank_documents(self, query, limit=32):
        scores = self.doc_bm25.get_scores(retrieval_tokens(query))
        return [self.ids[i] for i in sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:limit] if scores[i] > 0]

    def rank_windows(self, query, allowed, limit=32):
        scores = self.window_bm25.get_scores(retrieval_tokens(query))
        candidates = [i for i, (document_id, _, _) in enumerate(self.windows) if document_id in allowed]
        return sorted(candidates, key=lambda i: (-scores[i], i))[:limit]

    def expand(self, selected, context_chars=64000, padding=1100):
        # Preserve a literal parent-body slice; offsets and metadata remain auditable.
        spans = []
        for index in selected:
            document_id, start, end = self.windows[index]
            doc = self.documents[document_id]
            start, end = max(0, start-padding), min(len(doc.body), end+padding)
            overlaps = [i for i, (did, a, b) in enumerate(spans) if did == document_id and a <= end and start <= b]
            if overlaps:
                first = overlaps[0]
                start = min([start]+[spans[i][1] for i in overlaps])
                end = max([end]+[spans[i][2] for i in overlaps])
                spans[first] = (document_id, start, end)
                spans = [span for i, span in enumerate(spans) if i == first or i not in overlaps]
            else:
                spans.append((document_id, start, end))
        evidence, provenance, used = [], {}, 0
        for document_id, start, end in spans:
            doc = self.documents[document_id]
            text = doc.header+'\nBody:\n'+doc.body[start:end]
            if used+len(text) > context_chars:
                continue
            identifier = f'P{self.ids.index(document_id)}_{start}_{end}'
            evidence.append(Evidence(identifier, text, document_id))
            provenance[identifier] = {'document_id': document_id, 'body_start': start, 'body_end': end,
                                      'body_total_chars': len(doc.body)}
            used += len(text)
        # Use remaining capacity for complete modest-sized parent articles. This
        # enables legitimate report-content absence checks without dropping spans.
        for document_id in dict.fromkeys(e.source for e in evidence):
            doc = self.documents[document_id]
            if len(doc.body) > 12000:
                continue
            positions = [i for i, item in enumerate(evidence) if item.source == document_id]
            full_text = doc.header+'\nBody:\n'+doc.body
            previous_chars = sum(len(evidence[i].content) for i in positions)
            if used-previous_chars+len(full_text) > context_chars:
                continue
            identifier = f'P{self.ids.index(document_id)}_0_{len(doc.body)}'
            for i in positions:
                provenance.pop(evidence[i].evidence_id)
            first = positions[0]
            evidence[first] = Evidence(identifier, full_text, document_id)
            evidence = [item for i, item in enumerate(evidence) if i == first or i not in positions]
            provenance[identifier] = {'document_id': document_id, 'body_start': 0,
                                      'body_end': len(doc.body), 'body_total_chars': len(doc.body)}
            used = used-previous_chars+len(full_text)
        return evidence, provenance


class HybridParentRetriever:
    def __init__(self, index, graph_retriever, reranker, context_chars=64000):
        self.index, self.graph, self.reranker = index, graph_retriever, reranker
        self.context_chars = context_chars

    async def retrieve(self, question, facets, extra_queries=None, seed=None):
        extra_queries = list(extra_queries or [])[:2]
        queries = list(dict.fromkeys([question]+list(facets)[:4]+extra_queries))
        rankings = [self.index.rank_documents(query) for query in queries]
        graph_calls = []
        if seed is None:
            for mode, size in [('mix', 24), ('naive', 32)]:
                hits = await self.graph.search(question, mode=mode, top_k=size)
                rankings.append(list(dict.fromkeys(e.source for e in hits if e.source in self.index.documents)))
                graph_calls.append({'query': question, 'mode': mode, 'top_k': size})
        else:
            rankings.append(list(dict.fromkeys(e.source for e in seed if e.source in self.index.documents)))
            for query in extra_queries:
                hits = await self.graph.search(query, mode='mix', top_k=16)
                rankings.append(list(dict.fromkeys(e.source for e in hits if e.source in self.index.documents)))
                graph_calls.append({'query': query, 'mode': 'mix', 'top_k': 16})
        fused = reciprocal_rank_fusion(rankings)
        balanced = list(dict.fromkeys([item for ranking in rankings[:len(queries)] for item in ranking[:4]]+fused))[:64]
        allowed = set(balanced)
        ranked_windows = []
        for query in queries:
            candidates = self.index.rank_windows(query, allowed, 32)
            scores = await self.reranker.score(query, [self.index.window_text(i) for i in candidates])
            if len(scores) != len(candidates):
                raise ValueError('Reranker score count mismatch')
            order = sorted(zip(candidates, scores), key=lambda pair: (-pair[1], pair[0]))
            picked, per_doc = [], {}
            for index, score in order:
                document_id = self.index.windows[index][0]
                if per_doc.get(document_id, 0) >= 2:
                    continue
                picked.append(index)
                per_doc[document_id] = per_doc.get(document_id, 0)+1
                if len(picked) == 4:
                    break
            ranked_windows.append(picked)
        selected = []
        for position in range(4):
            for ranking in ranked_windows:
                if position < len(ranking) and ranking[position] not in selected:
                    selected.append(ranking[position])
                if len(selected) == 20:
                    break
            if len(selected) == 20:
                break
        evidence, provenance = self.index.expand(selected, self.context_chars)
        return evidence, {'method': 'BM25+LightRAG+RRF+crossencoder+parent-spans',
                          'queries': queries, 'graph_calls': graph_calls, 'candidate_documents': balanced,
                          'selected_windows': selected, 'provenance': provenance,
                          'context_chars': sum(len(e.content) for e in evidence)}
