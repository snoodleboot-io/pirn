"""``HttpEmbeddingProvider`` — provider-neutral HTTP/OpenAI-compatible embeddings.

Speaks the widely-adopted OpenAI-compatible ``/embeddings`` JSON shape
(``{"model", "input"}`` in, ``{"data": [{"embedding": [...]}, ...]}`` out) over
plain HTTP, so it works against any endpoint implementing that contract — no
vendor SDK, no hard vendor coupling. The endpoint, model, request path, and
auth are all configurable; the HTTP client (``httpx``) is imported lazily via
the ``[web]`` extra so importing this module stays backend-free.

Batching, client reuse, and retries come from
:class:`pirn_agents.embeddings.base_embedding_provider.BaseEmbeddingProvider`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.embeddings.base_embedding_provider import BaseEmbeddingProvider


class HttpEmbeddingProvider(BaseEmbeddingProvider):
    """Embed via an OpenAI-compatible HTTP ``/embeddings`` endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        credential: CredentialRef | None = None,
        path: str = "/embeddings",
        batch_size: int = 32,
        max_retries: int = 2,
        retry_base_delay: float = 0.0,
        timeout: float = 30.0,
        client: Any | None = None,
    ) -> None:
        """Initialise the HTTP embeddings adapter.

        Args:
            base_url: Root URL of the OpenAI-compatible embeddings service.
            model: Model identifier sent in every request body.
            credential: Optional bearer credential; when present its secret is
                sent as an ``Authorization: Bearer`` header.
            path: Request path appended to ``base_url`` (default
                ``"/embeddings"``).
            batch_size: Texts per HTTP round-trip (see the base provider).
            max_retries: Per-batch retry count (see the base provider).
            retry_base_delay: Backoff base seconds (see the base provider).
            timeout: Per-request timeout in seconds for the built client.
            client: Optional pre-built async HTTP client (an ``httpx.AsyncClient``
                or a compatible stub). When supplied it is reused and no backend
                import happens — the seam mirrored tests use to stay offline.

        Raises:
            TypeError: If ``credential`` is neither a ``CredentialRef`` nor
                ``None`` (validated by :class:`ConnectorBase`).
        """
        super().__init__(
            batch_size=batch_size,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            model=model,
            credential=credential,
        )
        self._base_url: str = base_url.rstrip("/")
        self._path: str = path if path.startswith("/") else f"/{path}"
        self._timeout: float = timeout
        self._injected_client: Any | None = client

    async def _create_client(self) -> Any:
        """Return the injected client, or lazily build an ``httpx.AsyncClient``."""
        if self._injected_client is not None:
            return self._injected_client
        httpx = _require("web", "httpx")
        headers: dict[str, str] = {}
        if self._credential is not None:
            headers["Authorization"] = f"Bearer {self._credential.reveal()}"
        return httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=self._timeout)

    async def _embed_batch(self, texts: Sequence[str], model: str | None) -> list[list[float]]:
        """POST one batch to the embeddings endpoint and parse the response.

        Args:
            texts: The batch of strings to embed.
            model: The model identifier for this request.

        Returns:
            One embedding vector per input string, ordered by the response's
            ``index`` field so ordering is robust to server reordering.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {"model": model, "input": list(texts)}
        response = await client.post(self._path, json=payload)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        rows: list[dict[str, Any]] = list(body["data"])
        ordered = sorted(rows, key=lambda item: item.get("index", 0))
        return [[float(x) for x in item["embedding"]] for item in ordered]
