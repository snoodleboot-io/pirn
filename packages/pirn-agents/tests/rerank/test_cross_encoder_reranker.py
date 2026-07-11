"""Tests for :class:`CrossEncoderReranker` using a stub model double.

A stub model injected via ``model_factory`` keeps these offline (no
``[cross-encoder]`` extra needed). The stub records the thread ``predict`` runs
on to prove scoring is offloaded off the event-loop thread.
"""

from __future__ import annotations

import threading
import unittest

import pytest

from pirn_agents.rerank.cross_encoder_reranker import CrossEncoderReranker


class StubCrossEncoder:
    """Records predict threads; scores pairs by the document text length."""

    def __init__(self) -> None:
        self.predict_threads: list[int] = []

    def predict(self, pairs: list[list[str]]) -> list[float]:
        self.predict_threads.append(threading.get_ident())
        return [float(len(document)) for _query, document in pairs]


class TestCrossEncoderReranker(unittest.IsolatedAsyncioTestCase):
    async def test_scores_documents_by_text_key(self) -> None:
        model = StubCrossEncoder()
        reranker = CrossEncoderReranker(model_name="stub", model_factory=lambda: model)

        scores = await reranker.score("q", [{"text": "aa"}, {"text": "bbbb"}])

        assert scores == [2.0, 4.0]

    async def test_empty_documents_short_circuits(self) -> None:
        model = StubCrossEncoder()
        reranker = CrossEncoderReranker(model_name="stub", model_factory=lambda: model)

        assert await reranker.score("q", []) == []
        assert model.predict_threads == []

    async def test_predict_is_thread_offloaded(self) -> None:
        model = StubCrossEncoder()
        reranker = CrossEncoderReranker(model_name="stub", model_factory=lambda: model)
        loop_thread = threading.get_ident()

        await reranker.score("q", [{"text": "abc"}])

        assert model.predict_threads
        assert all(tid != loop_thread for tid in model.predict_threads)

    async def test_falls_back_to_joined_values_without_text_key(self) -> None:
        model = StubCrossEncoder()
        reranker = CrossEncoderReranker(model_name="stub", model_factory=lambda: model)

        scores = await reranker.score("q", [{"body": "hello"}])

        assert scores == [float(len("hello"))]

    def test_real_backend_skipped_when_extra_absent(self) -> None:
        pytest.importorskip("sentence_transformers")
        reranker = CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
        assert isinstance(reranker, CrossEncoderReranker)


if __name__ == "__main__":
    unittest.main()
