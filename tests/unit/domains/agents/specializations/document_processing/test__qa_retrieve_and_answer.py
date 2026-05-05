"""Unit tests for :class:`_QARetrieveAndAnswer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._qa_retrieve_and_answer import (
    _QARetrieveAndAnswer,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubLLMProvider,
)


class TestQARetrieveAndAnswerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_no_content_response(self) -> None:
        llm = StubLLMProvider(["No content available."])
        embedder = StubEmbeddingProvider()
        with Tapestry() as t:
            _QARetrieveAndAnswer(
                chunks=[],
                question="What?",
                llm=llm,
                embedder=embedder,
                top_k=3,
                _config=KnotConfig(id="qa"),
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        response = result.outputs["qa"]
        self.assertIsInstance(response, AgentResponse)

    async def test_answers_question_from_chunks(self) -> None:
        llm = StubLLMProvider(["42"])
        vecs = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
        embedder = StubEmbeddingProvider(dimension=2, vectors=vecs)
        with Tapestry() as t:
            _QARetrieveAndAnswer(
                chunks=["chunk one", "chunk two"],
                question="Answer?",
                llm=llm,
                embedder=embedder,
                top_k=2,
                _config=KnotConfig(id="qa"),
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        response = result.outputs["qa"]
        self.assertIsInstance(response, AgentResponse)

    async def test_rejects_empty_question_at_process_time(self) -> None:
        with Tapestry():
            qa = _QARetrieveAndAnswer(
                chunks=["some text"],
                question="",
                llm=StubLLMProvider(["x"]),
                embedder=StubEmbeddingProvider(),
                top_k=1,
                _config=KnotConfig(id="qa"),
            )
        with self.assertRaises(TypeError):
            await qa.process(question="", chunks=["some text"])
