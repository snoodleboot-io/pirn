"""Tests for :class:`ContextualRetrievalPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.rerank.reranker_backend import RerankerBackend
from pirn_agents.specializations.rag.contextual_retrieval_pipeline import (
    ContextualRetrievalPipeline,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class _RelevantFirstReranker(RerankerBackend):
    """Scores a document higher when it contains the ``target`` marker."""

    def __init__(self, target: str) -> None:
        self._target = target

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        return [1.0 if self._target in str(doc.get("text", "")) else 0.0 for doc in documents]


class TestContextualRetrievalPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_reranks_compresses_and_synthesizes(self) -> None:
        memory = StubMemoryStore(
            [
                {"id": "1", "text": "irrelevant noise"},
                {"id": "2", "text": "the TARGET answer lives here"},
            ]
        )
        # Backend reranks -> only doc 2 survives to rerank_k=1; compression then
        # synthesis each make one LLM call.
        llm = StubLLMProvider(["TARGET answer", "final grounded answer"])
        reranker = _RelevantFirstReranker(target="TARGET")
        with Tapestry() as t:
            ContextualRetrievalPipeline(
                query="what is the target?",
                memory=memory,
                llm=llm,
                reranker=reranker,
                fetch_k=10,
                rerank_k=1,
                _config=KnotConfig(id="ctx"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["ctx"]
        assert isinstance(response, AgentResponse)
        assert response.content == "final grounded answer"
        # Synthesis prompt carries the compressed relevant span only.
        synth_prompt = llm.calls[-1][-1]["content"]
        assert "TARGET answer" in synth_prompt

    async def test_rejects_non_positive_rerank_k(self) -> None:
        knot = ContextualRetrievalPipeline(
            query="q",
            memory=StubMemoryStore([]),
            llm=StubLLMProvider(["a"]),
            _config=KnotConfig(id="ctx"),
        )
        with self.assertRaisesRegex(ValueError, "rerank_k must be a positive int"):
            await knot.process(
                query="q", memory=StubMemoryStore([]), llm=StubLLMProvider(["a"]), rerank_k=0
            )
