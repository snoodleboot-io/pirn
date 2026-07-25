"""Unit tests for :class:`_QARetrieveAndAnswer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._qa_retrieve_and_answer import (
    _QARetrieveAndAnswer,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubEmbeddingProvider,
    StubLLMProvider,
)


def _make_knot(llm: StubLLMProvider, embedder: StubEmbeddingProvider) -> _QARetrieveAndAnswer:
    with Tapestry():
        return _QARetrieveAndAnswer(
            chunks=[],
            question="q",
            llm=llm,
            embedder=embedder,
            top_k=3,
            _config=KnotConfig(id="qa"),
        )


class TestQARetrieveAndAnswerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_no_content_response(self) -> None:
        llm = StubLLMProvider(["No content available."])
        embedder = StubEmbeddingProvider()
        k = _make_knot(llm, embedder)
        response = await k.process(chunks=[], question="What?", llm=llm, embedder=embedder, top_k=3)
        self.assertIsInstance(response, AgentResponse)

    async def test_answers_question_from_chunks(self) -> None:
        llm = StubLLMProvider(["42"])
        vecs = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
        embedder = StubEmbeddingProvider(dimension=2, vectors=vecs)
        k = _make_knot(llm, embedder)
        response = await k.process(
            chunks=["chunk one", "chunk two"],
            question="Answer?",
            llm=llm,
            embedder=embedder,
            top_k=2,
        )
        self.assertIsInstance(response, AgentResponse)

    async def test_rejects_empty_question(self) -> None:
        llm = StubLLMProvider(["x"])
        embedder = StubEmbeddingProvider()
        k = _make_knot(llm, embedder)
        with self.assertRaises(TypeError):
            await k.process(chunks=["some text"], question="", llm=llm, embedder=embedder, top_k=1)
