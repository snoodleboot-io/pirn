"""Async ``ApiClient`` wrapper around the OpenMetadata REST API.

Uses ``httpx.AsyncClient`` with a bearer-token ``Authorization`` header
populated from ``config.jwt_token``. The generic :meth:`request` forwards
method/path/params/body/headers to ``client.request`` and returns the
parsed JSON body.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.open_metadata_config import (
    OpenMetadataConfig,
)
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class OpenMetadataClient(ApiClient):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: OpenMetadataConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "OpenMetadataClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OpenMetadataConfig | None:
        return self._config

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        client = await self._ensure_client()
        url = self._full_url(path)
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None
        try:
            response = await client.request(
                method.upper(),
                url,
                params=request_params,
                json=request_body,
                headers=request_headers,
            )
            return response.json()
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

    async def close(self) -> None:
        if self._client is not None:
            aclose_fn = getattr(self._client, "aclose", None)
            if callable(aclose_fn):
                await aclose_fn()
            self._client = None
        self._closed = True
        self._logger.debug("open_metadata.close")

    def _full_url(self, path: str) -> str:
        base = self._config.host_url if self._config is not None else None
        if path.startswith("http"):
            return path
        if base is None:
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("OpenMetadataClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OpenMetadataClient requires httpx; install via "
                "`pip install pirn[open-metadata]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "OpenMetadataClient: missing config and no injected client"
            )
        if self._config.host_url is None:
            raise RuntimeError(
                "OpenMetadataClient: config.host_url is required"
            )
        if self._config.jwt_token is None:
            raise RuntimeError(
                "OpenMetadataClient: config.jwt_token is required"
            )
        try:
            client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self._config.jwt_token}"
                }
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("open_metadata.connect")
        return client
