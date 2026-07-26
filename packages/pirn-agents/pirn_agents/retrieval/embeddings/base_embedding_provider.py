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
* **retries** — each batch is retried on failure per a composed
  :class:`~pirn_agents.llm.retry_policy.RetryPolicy` (the same jittered,
  capped exponential schedule the fan-out engines use), not a hand-rolled
  ``2**attempt`` formula.

Client pooling, teardown, and credential scrubbing come from
:class:`pirn.connectors.connector_base.ConnectorBase` — the same base
:class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` inherits, so an
embedding adapter and an LLM adapter share one pooling lifecycle rather than two
copies of it. The public surface aligns with
:class:`pirn_agents.retrieval.embeddings.embedding_provider.EmbeddingProvider`: :meth:`embed` and
:meth:`close`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator, Sequence

from pirn.connectors.connector_base import ConnectorBase
from pirn.security.credential_ref import CredentialRef

from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider


class BaseEmbeddingProvider(ConnectorBase, EmbeddingProvider):
    """Batching, retrying, client-reusing base for embedding adapters.

    Mirrors :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider`: the
    ``ConnectorBase`` pooling lifecycle (``_get_client`` / ``_create_client`` /
    ``close`` / ``_clear_credentials``) is inherited, not re-implemented, and only
    the embedding-specific batching layers on top.
    """

    # Optional backends (httpx, sentence-transformers) ship with pirn-agents, so
    # the missing-dependency install hint must name this distribution, not core's.
    _install_dist = "pirn-agents"

    def __init__(
        self,
        *,
        batch_size: int = 32,
        retry_policy: RetryPolicy | None = None,
        rng: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        model: str | None = None,
        credential: CredentialRef | None = None,
    ) -> None:
        """Initialise the batching base.

        Args:
            batch_size: Maximum number of texts sent to the backend per
                round-trip. Must be a positive integer.
            retry_policy: How many times, and how long, to back off between
                per-batch retries. Defaults to :class:`RetryPolicy` — the same
                jittered, capped exponential schedule the fan-out engines use
                (2 retries, 0.05s base, full jitter). Pass
                ``RetryPolicy(max_retries=0)`` to disable retrying, or
                ``RetryPolicy(base_delay=0.0)`` to retry instantly.
            rng: Optional zero-arg ``() -> float in [0, 1)`` used for the jitter
                draw; defaults to :func:`random.random`. Injected in tests for
                deterministic delays.
            sleep: Optional awaitable inter-attempt sleep; defaults to
                :func:`asyncio.sleep`. Injected in tests to stay instant.
            model: Default model identifier used when :meth:`embed` is called
                without an explicit ``model``.
            credential: Optional :class:`CredentialRef` for the backend client,
                stored and scrubbed by :class:`ConnectorBase`.

        Raises:
            ValueError: If ``batch_size`` is not a positive int.
            TypeError: If ``retry_policy`` is not a :class:`RetryPolicy`, or if
                ``credential`` is neither a ``CredentialRef`` nor ``None``
                (the latter raised by :class:`ConnectorBase`).
        """
        super().__init__(credential=credential)
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive int, got {batch_size!r}")
        resolved_policy = retry_policy if retry_policy is not None else RetryPolicy()
        if not isinstance(resolved_policy, RetryPolicy):
            raise TypeError(
                f"retry_policy must be a RetryPolicy, got {type(retry_policy).__name__}"
            )
        self._batch_size: int = batch_size
        self._retry_policy: RetryPolicy = resolved_policy
        self._rng: Callable[[], float] | None = rng
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )
        self._default_model: str | None = model

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
        """Embed one batch, retrying on failure per the composed ``RetryPolicy``."""
        attempt = 0
        while True:
            try:
                return await self._embed_batch(batch, model)
            except Exception:
                if attempt >= self._retry_policy.max_retries:
                    raise
                await self._backoff(attempt)
                attempt += 1

    async def _backoff(self, attempt: int) -> None:
        """Sleep for the policy's delay before retry ``attempt`` (0-based)."""
        delay = self._retry_policy.backoff_delay(attempt, rng=self._rng)
        if delay > 0:
            await self._sleep(delay)

    @staticmethod
    def _iter_batches(items: list[str], size: int) -> Iterator[list[str]]:
        """Yield ``items`` in contiguous chunks of at most ``size``."""
        for start in range(0, len(items), size):
            yield items[start : start + size]
