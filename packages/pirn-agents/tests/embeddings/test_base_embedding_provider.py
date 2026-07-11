"""Tests for :class:`BaseEmbeddingProvider` batching, client reuse, and retries.

Uses a recording subclass double (no backend) so batch splitting, one-time
client construction, and retry-on-failure are asserted on exact call shapes.
"""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from typing import Any

from pirn_agents.embeddings.base_embedding_provider import BaseEmbeddingProvider


class RecordingProvider(BaseEmbeddingProvider):
    """Records every batch and counts client builds; embeds deterministically."""

    def __init__(self, *, fail_times: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.batches: list[list[str]] = []
        self.client_builds = 0
        self._fail_times = fail_times
        self._attempts = 0

    async def _create_client(self) -> Any:
        self.client_builds += 1
        return object()

    async def _embed_batch(self, texts: Sequence[str], model: str | None) -> list[list[float]]:
        await self._get_client()
        self._attempts += 1
        if self._attempts <= self._fail_times:
            raise RuntimeError("transient failure")
        self.batches.append(list(texts))
        return [[float(len(text)), float(model is not None)] for text in texts]


class TestBaseEmbeddingProvider(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_positive_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            RecordingProvider(batch_size=0)

    def test_rejects_negative_max_retries(self) -> None:
        with self.assertRaises(ValueError):
            RecordingProvider(max_retries=-1)

    async def test_rejects_bare_str_input(self) -> None:
        provider = RecordingProvider(batch_size=2)
        with self.assertRaises(TypeError):
            await provider.embed("not-a-sequence")  # type: ignore[arg-type]

    async def test_splits_into_fixed_size_batches_in_order(self) -> None:
        provider = RecordingProvider(batch_size=2)

        vectors = await provider.embed(["a", "bb", "ccc", "dddd", "eeeee"])

        assert provider.batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
        # one vector per input, in input order (length encoded in first component)
        assert [vec[0] for vec in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]

    async def test_client_built_once_across_batches_and_calls(self) -> None:
        provider = RecordingProvider(batch_size=1)

        await provider.embed(["a", "b", "c"])
        await provider.embed(["d"])

        assert provider.client_builds == 1

    async def test_default_model_is_forwarded(self) -> None:
        provider = RecordingProvider(batch_size=2, model="default-model")

        vectors = await provider.embed(["a"])

        # second component encodes model-is-not-None
        assert vectors[0][1] == 1.0

    async def test_retries_until_success(self) -> None:
        provider = RecordingProvider(batch_size=2, max_retries=2, fail_times=2)

        vectors = await provider.embed(["a", "b"])

        assert len(vectors) == 2
        assert provider.batches == [["a", "b"]]

    async def test_raises_after_exhausting_retries(self) -> None:
        provider = RecordingProvider(batch_size=2, max_retries=1, fail_times=5)

        with self.assertRaises(RuntimeError):
            await provider.embed(["a", "b"])

    async def test_empty_input_returns_empty(self) -> None:
        provider = RecordingProvider(batch_size=2)

        assert await provider.embed([]) == []
        assert provider.batches == []

    async def test_close_is_idempotent(self) -> None:
        provider = RecordingProvider(batch_size=2)
        await provider.embed(["a"])

        await provider.close()
        await provider.close()

        assert provider._client is None


if __name__ == "__main__":
    unittest.main()
