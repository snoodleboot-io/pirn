"""Async ``ApiClient`` wrapper around the Alation REST API.

Alation uses a refresh-token + access-token flow. The simplest correct
shape — and the one used here — is to send the refresh token in the
``Token`` request header (Alation's conventional name) on every call.
Richer access-token exchange can be layered on by subclasses or by
injecting an already-authorised ``client=``.

The generic :meth:`request` forwards method/path/params/body/headers to
``httpx.AsyncClient.request`` and returns the parsed JSON body.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.alation_config import AlationConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class AlationClient(ApiClient):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: AlationConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "AlationClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AlationConfig | None:
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
        self._logger.debug("alation.close")

    def _full_url(self, path: str) -> str:
        base = self._config.base_url if self._config is not None else None
        if path.startswith("http"):
            return path
        if base is None:
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AlationClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AlationClient requires httpx; install via "
                "`pip install pirn[alation]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "AlationClient: missing config and no injected client"
            )
        if self._config.base_url is None:
            raise RuntimeError(
                "AlationClient: config.base_url is required"
            )
        if self._config.refresh_token is None:
            raise RuntimeError(
                "AlationClient: config.refresh_token is required"
            )
        try:
            client = httpx.AsyncClient(
                headers={"Token": self._config.refresh_token}
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("alation.connect")
        return client
