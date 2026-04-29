from __future__ import annotations

from typing import Any


class _LazyClient:
    """Wraps either an injected client (test / sharing) or a GlideClientConfiguration.

    When a config is given the GlideClient is created lazily on first use.
    """

    def __init__(self, client: Any = None, config: Any = None) -> None:
        if client is None and config is None:
            raise TypeError("provide either client= or config=")
        self._client = client
        self._config = config

    async def get(self) -> Any:
        if self._client is None:
            try:
                from glide import GlideClient
            except ImportError as exc:
                raise ImportError(
                    "ValKey backends require valkey-glide; install via "
                    "`pip install pirn[valkey]`"
                ) from exc
            self._client = await GlideClient.create(self._config)
        return self._client

    async def close(self) -> None:
        if self._client is not None and self._config is not None:
            await self._client.close()
            self._client = None
