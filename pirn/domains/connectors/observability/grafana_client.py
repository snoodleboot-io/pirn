"""Async ``ApiClient`` wrapper around the Grafana HTTP REST API.

Grafana exposes a fully-documented HTTP REST API at
``/api/dashboards``, ``/api/datasources``, ``/api/folders`` etc.
Authentication uses a bearer token (API key or service-account token).
The connector uses :mod:`httpx` directly (``pirn[grafana]`` extra
declares the dependency).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.observability.grafana_config import GrafanaConfig


class GrafanaClient(ApiClient):
    """Concrete :class:`ApiClient` for the Grafana HTTP REST API."""

    def __init__(
        self,
        config: GrafanaConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "GrafanaClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GrafanaConfig | None:
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
        if not isinstance(method, str) or not method:
            raise ValueError(
                "GrafanaClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "GrafanaClient.request: path must be non-empty"
            )
        client = await self._ensure_client()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        try:
            response = await client.request(
                method.upper(),
                path,
                params=request_params,
                json=request_body,
                headers=request_headers,
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client is not None:
            aclose = getattr(self._client, "aclose", None)
            if callable(aclose):
                await aclose()
            self._client = None
        self._closed = True
        self._logger.debug("grafana.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("GrafanaClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "GrafanaClient requires httpx; install via "
                "`pip install pirn[grafana]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "GrafanaClient: missing config and no injected client"
            )
        if self._config.base_url is None:
            raise RuntimeError(
                "GrafanaClient: config.base_url is required"
            )

        client_headers: dict[str, str] = {}
        if self._config.api_key is not None:
            client_headers["Authorization"] = (
                f"Bearer {self._config.api_key}"
            )

        try:
            client = httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/"),
                headers=client_headers or None,
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("grafana.connect")
        return client
