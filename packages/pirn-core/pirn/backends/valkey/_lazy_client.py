from __future__ import annotations

from typing import Any

from pirn.core.optional_dependency import OptionalDependency


class _LazyClient:
    """Wraps either an injected client (test / sharing) or a GlideClientConfiguration.

    When a config is given the GlideClient is created lazily on first use.
    """

    def __init__(self, client: Any = None, config: Any = None) -> None:
        """Initialise the wrapper.

        Args:
            client: An existing ``GlideClient`` instance.  If provided, it is
                returned immediately from :meth:`get`.
            config: A ``GlideClientConfiguration`` used to create a client
                lazily on first :meth:`get` call.  Mutually exclusive with
                ``client``.

        Raises:
            TypeError: If neither ``client`` nor ``config`` is provided.
        """
        if client is None and config is None:
            raise TypeError("provide either client= or config=")
        self._client = client
        self._config = config

    async def get(self) -> Any:
        """Return the ValKey client, creating it lazily if needed.

        Returns:
            A ``GlideClient`` instance.

        Raises:
            ImportError: If ``valkey-glide`` is not installed.
        """
        if self._client is None:
            glide = OptionalDependency.require("glide", extra="valkey")
            self._client = await glide.GlideClient.create(self._config)
        return self._client

    async def close(self) -> None:
        """Close the client if it was created internally from a config.

        Injected clients (passed as ``client=``) are not closed here; the
        caller owns their lifecycle.
        """
        if self._client is not None and self._config is not None:
            await self._client.close()
            self._client = None
