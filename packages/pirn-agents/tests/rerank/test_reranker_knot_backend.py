"""Tests that the existing RAG :class:`Reranker` knot uses a ``RerankerBackend``.

Covers PAE-F4-S7-T1's wiring: the knot accepts a provider-neutral backend, ranks
by its scores, validates its type, and requires exactly one of ``llm`` /
``reranker``. The LLM path stays unchanged (covered by the existing rerank test).
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.reranker import Reranker
from tests.rerank.test_reranker_backend import StubReranker


class TestRerankerKnotBackend(unittest.IsolatedAsyncioTestCase):
    async def test_backend_ranks_documents_top_k(self) -> None:
        docs = [{"text": "low"}, {"text": "high"}, {"text": "mid"}]
        backend = StubReranker([0.2, 0.9, 0.5])
        knot = Reranker(
            query="q",
            documents=docs,
            reranker=backend,
            top_k=2,
            _config=KnotConfig(id="rerank"),
        )

        reranked = await knot.process(query="q", documents=docs, reranker=backend, top_k=2)

        assert reranked == [{"text": "high"}, {"text": "mid"}]
        assert backend.calls == ["q"]

    async def test_backend_path_needs_no_llm(self) -> None:
        docs = [{"text": "a"}, {"text": "b"}]
        backend = StubReranker([0.1, 0.9])
        knot = Reranker(
            query="q", documents=docs, reranker=backend, _config=KnotConfig(id="rerank")
        )
        reranked = await knot.process(query="q", documents=docs, reranker=backend)
        assert reranked[0] == {"text": "b"}

    async def test_rejects_non_backend_reranker(self) -> None:
        knot = Reranker(query="q", documents=[], reranker=None, _config=KnotConfig(id="rerank"))
        with self.assertRaisesRegex(TypeError, "reranker must be a RerankerBackend"):
            await knot.process(query="q", documents=[{"text": "a"}], reranker=object())  # type: ignore[arg-type]

    async def test_requires_llm_or_reranker(self) -> None:
        knot = Reranker(query="q", documents=[], _config=KnotConfig(id="rerank"))
        with self.assertRaisesRegex(ValueError, "either llm or reranker"):
            await knot.process(query="q", documents=[{"text": "a"}])

    async def test_backend_used_through_tapestry_run(self) -> None:
        docs = [{"text": "x"}, {"text": "y"}]
        backend = StubReranker([0.3, 0.7])
        with Tapestry() as tapestry:
            Reranker(
                query="q",
                documents=docs,
                reranker=backend,
                top_k=1,
                _config=KnotConfig(id="rerank"),
            )
        result = await tapestry.run(RunRequest())
        assert result.succeeded
        assert result.outputs["rerank"] == [{"text": "y"}]


if __name__ == "__main__":
    unittest.main()
