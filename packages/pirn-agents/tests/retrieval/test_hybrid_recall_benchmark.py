"""Fixture recall benchmark: hybrid beats pure-dense (PAE-F4-S6-T4).

Builds a fixture where dense retrieval structurally fails — every query's dense
vector points at distractors and each relevant document is orthogonal to it — so
dense recall is 0, while the relevant document carries a unique keyword that BM25
nails. Fusing the two arms recovers the relevant document, so hybrid recall
strictly beats pure-dense recall. This validates the feature acceptance
criterion; measured recall is printed for an F10-style report.
"""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.bm25_index import Bm25Index
from pirn_agents.retrieval.hybrid_retriever import HybridRetriever
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_record import VectorRecord
from tests.vector_stores.conformance import FixedEmbedder


def _build_fixture() -> tuple[list[VectorRecord], Bm25Index, list[tuple[str, str]]]:
    """Return (records, lexical index, [(query, relevant_id)])."""
    index = Bm25Index()
    queries: list[tuple[str, str]] = []
    records: list[VectorRecord] = []

    # 12 distractors all aligned with the query vector [1, 0]; they crowd out
    # dense top-k for every query.
    for i in range(12):
        did = f"distractor-{i}"
        records.append(
            VectorRecord.create(id=did, vector=[1.0, 0.0], document="common filler text")
        )
        index.add(did, "common filler text")

    # 5 relevant docs orthogonal to the query vector (dense cosine 0), each
    # carrying a unique keyword the matching query uses.
    for i in range(5):
        rid = f"relevant-{i}"
        keyword = f"rarekeyword{i}"
        records.append(VectorRecord.create(id=rid, vector=[0.0, 1.0], document=f"{keyword} filler"))
        index.add(rid, f"{keyword} filler")
        queries.append((keyword, rid))

    return records, index, queries


def _make_retriever() -> HybridRetriever:
    with Tapestry():
        knot = HybridRetriever.__new__(HybridRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="hybrid-bench"))
    return knot


@pytest.mark.benchmark
async def test_hybrid_recall_beats_pure_dense() -> None:
    records, index, queries = _build_fixture()
    store = InMemoryVectorStore()
    await store.upsert(records)
    retriever = _make_retriever()
    embedder = FixedEmbedder([1.0, 0.0])
    top_k = 3

    dense_hits = 0
    hybrid_hits = 0
    for query, relevant_id in queries:
        dense_matches = await store.query([1.0, 0.0], top_k=top_k)
        if relevant_id in {m.id for m in dense_matches}:
            dense_hits += 1
        hybrid = await retriever.process(
            query=query,
            store=store,
            lexical=index,
            embedder=embedder,
            top_k=top_k,
        )
        if relevant_id in {hit["id"] for hit in hybrid}:
            hybrid_hits += 1

    dense_recall = dense_hits / len(queries)
    hybrid_recall = hybrid_hits / len(queries)

    assert hybrid_recall > dense_recall
    assert hybrid_recall == 1.0
    print(
        f"[benchmark] recall@{top_k} dense={dense_recall:.2f} hybrid={hybrid_recall:.2f} "
        f"over {len(queries)} queries"
    )
