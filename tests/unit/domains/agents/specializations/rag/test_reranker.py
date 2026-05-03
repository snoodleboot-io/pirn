"""Tests for :class:`Reranker`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.reranker import Reranker
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestRerankerConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                Reranker(
                    query="q",
                    documents=[],
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="rerank"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        llm = StubLLMProvider(["0.9"])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                Reranker(
                    query="q",
                    documents=[],
                    llm=llm,
                    top_k=0,
                    _config=KnotConfig(id="rerank"),
                )


@pytest.mark.asyncio
class TestRerankerHappyPath:
    async def test_returns_empty_for_empty_documents(self) -> None:
        llm = StubLLMProvider([])
        with Tapestry() as t:
            Reranker(
                query="test",
                documents=[],
                llm=llm,
                top_k=3,
                _config=KnotConfig(id="rerank"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["rerank"] == []

    async def test_reranks_and_returns_top_k(self) -> None:
        docs = [
            {"text": "low relevance doc"},
            {"text": "high relevance doc"},
            {"text": "medium relevance doc"},
        ]
        llm = StubLLMProvider(["0.2", "0.9", "0.5"])
        with Tapestry() as t:
            Reranker(
                query="find high relevance",
                documents=docs,
                llm=llm,
                top_k=2,
                _config=KnotConfig(id="rerank"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        reranked = result.outputs["rerank"]
        assert len(reranked) == 2
        assert reranked[0] == docs[1]
        assert reranked[1] == docs[2]

    async def test_handles_non_numeric_score_gracefully(self) -> None:
        docs = [{"text": "doc a"}, {"text": "doc b"}]
        llm = StubLLMProvider(["not-a-number", "0.8"])
        with Tapestry() as t:
            Reranker(
                query="q",
                documents=docs,
                llm=llm,
                top_k=2,
                _config=KnotConfig(id="rerank"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        reranked = result.outputs["rerank"]
        assert len(reranked) == 2
        assert reranked[0] == docs[1]
