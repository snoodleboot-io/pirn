"""``LocalEmbeddingProvider`` — local sentence-transformer embeddings.

Runs a `sentence-transformers` model entirely in-process (zero network) behind
the ``[local-embed]`` extra. The heavy ``sentence_transformers`` import is lazy
so importing this module stays backend-free, and every ``encode`` call is
offloaded to a worker thread via :func:`asyncio.to_thread` so the synchronous,
CPU-bound model inference never blocks the event loop.

Batching, client (model) reuse, and retries come from
:class:`pirn_agents.embeddings.base_embedding_provider.BaseEmbeddingProvider`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.embeddings.base_embedding_provider import BaseEmbeddingProvider


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Embed with an in-process sentence-transformer model, thread-offloaded."""

    def __init__(
        self,
        *,
        model_name: str,
        batch_size: int = 32,
        max_retries: int = 0,
        model_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the local embedding adapter.

        Args:
            model_name: Name/path of the sentence-transformer model to load.
            batch_size: Texts per ``encode`` call (see the base provider).
            max_retries: Per-batch retry count; defaults to ``0`` since local
                inference is deterministic and non-transient.
            model_factory: Optional zero-arg factory returning a pre-built model
                object exposing ``encode``. When supplied it replaces the lazy
                ``sentence_transformers`` load — the seam mirrored tests use to
                run offline without the extra installed.
        """
        super().__init__(batch_size=batch_size, max_retries=max_retries, model=model_name)
        self._model_name: str = model_name
        self._model_factory: Callable[[], Any] | None = model_factory

    async def _create_client(self) -> Any:
        """Return the factory-built model, or lazily load a ``SentenceTransformer``."""
        if self._model_factory is not None:
            return self._model_factory()
        sentence_transformers = _require("local-embed", "sentence_transformers")
        return sentence_transformers.SentenceTransformer(self._model_name)

    async def _embed_batch(self, texts: Sequence[str], model: str | None) -> list[list[float]]:
        """Encode one batch on a worker thread so the event loop stays free.

        Args:
            texts: The batch of strings to embed.
            model: Unused; the model is fixed at construction. Present to satisfy
                the base hook signature.

        Returns:
            One embedding vector per input string, in input order.
        """
        client = await self._get_client()
        batch = list(texts)

        def _encode() -> Any:
            return client.encode(batch)

        raw = await asyncio.to_thread(_encode)
        return [[float(value) for value in row] for row in raw]
