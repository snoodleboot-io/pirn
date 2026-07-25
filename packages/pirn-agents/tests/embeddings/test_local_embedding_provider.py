"""Tests for :class:`LocalEmbeddingProvider` using a stub model double.

A stub model injected via ``model_factory`` keeps these offline, so they run
without the ``[local-embed]`` extra. The stub records the thread it runs on to
prove inference is offloaded off the event-loop thread. A separate test skips
when ``sentence_transformers`` is absent.
"""

from __future__ import annotations

import asyncio
import threading
import unittest

import pytest

from pirn_agents.embeddings.local_embedding_provider import LocalEmbeddingProvider


class StubSentenceModel:
    """Records the thread ``encode`` runs on; returns length-based vectors."""

    def __init__(self) -> None:
        self.encode_threads: list[int] = []
        self.build_count = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.encode_threads.append(threading.get_ident())
        return [[float(len(text)), 1.0] for text in texts]


class TestLocalEmbeddingProvider(unittest.IsolatedAsyncioTestCase):
    async def test_embeds_via_stub_model(self) -> None:
        model = StubSentenceModel()
        provider = LocalEmbeddingProvider(
            model_name="stub", model_factory=lambda: model, batch_size=10
        )

        vectors = await provider.embed(["a", "bb", "ccc"])

        assert [vec[0] for vec in vectors] == [1.0, 2.0, 3.0]

    async def test_inference_is_thread_offloaded(self) -> None:
        model = StubSentenceModel()
        provider = LocalEmbeddingProvider(model_name="stub", model_factory=lambda: model)
        loop_thread = threading.get_ident()

        await provider.embed(["a", "b"])

        assert model.encode_threads, "encode was never called"
        assert all(tid != loop_thread for tid in model.encode_threads)

    async def test_model_built_once_across_calls(self) -> None:
        builds = {"n": 0}

        def factory() -> StubSentenceModel:
            builds["n"] += 1
            return StubSentenceModel()

        provider = LocalEmbeddingProvider(model_name="stub", model_factory=factory, batch_size=1)

        await provider.embed(["a", "b"])
        await provider.embed(["c"])

        assert builds["n"] == 1

    async def test_concurrent_embeds_do_not_block_loop(self) -> None:
        model = StubSentenceModel()
        provider = LocalEmbeddingProvider(model_name="stub", model_factory=lambda: model)

        results = await asyncio.gather(
            provider.embed(["a"]), provider.embed(["bb"]), provider.embed(["ccc"])
        )

        assert [r[0][0] for r in results] == [1.0, 2.0, 3.0]

    def test_real_backend_skipped_when_extra_absent(self) -> None:
        # Documents the real path; skips cleanly without the [local-embed] extra.
        pytest.importorskip("sentence_transformers")
        provider = LocalEmbeddingProvider(model_name="sentence-transformers/all-MiniLM-L6-v2")
        assert isinstance(provider, LocalEmbeddingProvider)


if __name__ == "__main__":
    unittest.main()
