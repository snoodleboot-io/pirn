"""Recording stub :class:`MLEmbeddingProvider` for tests."""

from __future__ import annotations

from collections.abc import Sequence

from pirn_ml.ml_embedding_provider import MLEmbeddingProvider


class RecordingEmbeddingProvider(MLEmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.closed: bool = False

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        self.calls.append((list(texts), model))
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def close(self) -> None:
        self.closed = True
