"""``BaseEmbeddingProvider`` — batching, client reuse, and retries for embeddings.

Concrete embedding adapters (HTTP, local sentence-transformer, ...) subclass
this base and implement two hooks:

* :meth:`_create_client` — build the backend client once (the pooling lever);
* :meth:`_embed_batch` — embed a single already-sized batch of texts.

The base then layers three cross-cutting behaviours every adapter shares:

* **batching by default** — :meth:`embed` splits its input into fixed-size
  batches (configurable) so a large call becomes a bounded number of backend
  round-trips;
* **async client reuse** — the backend client is constructed once via
  :meth:`_get_client` and reused for every batch and every call;
* **retries** — each batch is retried on failure up to ``max_retries`` with
  optional exponential backoff.

It aligns with
:class:`pirn.core.providers.embedding_provider.EmbeddingProvider`: the public
surface is :meth:`embed` and :meth:`close`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from typing import Any

from pirn.core.providers.embedding_provider import EmbeddingProvider


class BaseEmbeddingProvider(EmbeddingProvider):
    """Batching, retrying, client-reusing base for embedding adapters."""

    def __init__(
        self,
        *,
        batch_size: int = 32,
        max_retries: int = 2,
        retry_base_delay: float = 0.0,
        model: str | None = None,
    ) -> None:
        """Initialise the batching base.

        Args:
            batch_size: Maximum number of texts sent to the backend per
                round-trip. Must be a positive integer.
            max_retries: Number of retries attempted per batch after the first
                failure. Must be a non-negative integer.
            retry_base_delay: Base seconds for exponential backoff between
                retries; ``0.0`` retries immediately. Must be non-negative.
            model: Default model identifier used when :meth:`embed` is called
                without an explicit ``model``.

        Raises:
            ValueError: If ``batch_size`` is not a positive int, ``max_retries``
                is negative, or ``retry_base_delay`` is negative.
        """
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive int, got {batch_size!r}")
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError(f"max_retries must be a non-negative int, got {max_retries!r}")
        if retry_base_delay < 0:
            raise ValueError(f"retry_base_delay must be non-negative, got {retry_base_delay!r}")
        self._batch_size: int = batch_size
        self._max_retries: int = max_retries
        self._retry_base_delay: float = retry_base_delay
        self._default_model: str | None = model
        self._client: Any | None = None

    async def _get_client(self) -> Any:
        """Return the backend client, constructing it once and caching it."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        """Build and return the backend client. Overridden by concrete adapters.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _create_client()")

    async def _embed_batch(self, texts: Sequence[str], model: str | None) -> list[list[float]]:
        """Embed one already-sized batch. Overridden by concrete adapters.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _embed_batch()")

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        """Return one embedding vector per input string, in input order.

        The input is split into batches of at most ``batch_size`` and each batch
        is embedded with retries against the reused backend client.

        Args:
            texts: The strings to embed.
            model: Optional per-call model override; falls back to the default
                model supplied at construction.

        Returns:
            One embedding vector (list of floats) per input string, in order.

        Raises:
            TypeError: If ``texts`` is a bare ``str`` rather than a sequence of
                strings.
        """
        if isinstance(texts, str):
            raise TypeError("texts must be a sequence of strings, not a single str")
        resolved_model = model if model is not None else self._default_model
        items = list(texts)
        out: list[list[float]] = []
        for batch in self._iter_batches(items, self._batch_size):
            out.extend(await self._embed_with_retry(batch, resolved_model))
        return out

    async def _embed_with_retry(self, batch: Sequence[str], model: str | None) -> list[list[float]]:
        """Embed one batch, retrying on failure up to ``max_retries`` times."""
        attempt = 0
        while True:
            try:
                return await self._embed_batch(batch, model)
            except Exception:
                if attempt >= self._max_retries:
                    raise
                attempt += 1
                if self._retry_base_delay > 0:
                    await asyncio.sleep(self._retry_base_delay * (2 ** (attempt - 1)))

    @staticmethod
    def _iter_batches(items: list[str], size: int) -> Iterator[list[str]]:
        """Yield ``items`` in contiguous chunks of at most ``size``."""
        for start in range(0, len(items), size):
            yield items[start : start + size]

    async def close(self) -> None:
        """Release the reused backend client and scrub credentials.

        The client's async ``aclose`` is awaited when present, else its sync
        ``close`` is called; the reference is dropped and credentials cleared.
        Calling ``close`` again is a safe no-op.
        """
        client: Any = self._client
        if client is not None:
            if callable(getattr(client, "aclose", None)):
                await client.aclose()
            elif callable(getattr(client, "close", None)):
                client.close()
            self._client = None
        self._clear_credentials()

    def _clear_credentials(self) -> None:
        """Drop any in-memory credential so the secret becomes GC-able."""
        self._config = None
