"""Async ``ApiClient`` wrapper around the Airbyte REST API.

Uses ``httpx.AsyncClient`` with a bearer-token ``Authorization`` header.
``request`` forwards method/path/params/body/headers to ``client.request``
and returns the parsed JSON body.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``resource`` (``connections``, ``workspaces``, ...) using Airbyte
  Cloud's POST-based listing.
* Vendor-typed shortcuts :meth:`list_connections` and
  :meth:`list_workspaces`.

Authentication. Either configure an ``access_token`` directly, or configure the
OAuth2 client-credentials pair (``client_id`` / ``client_secret``) and let
:meth:`_exchange_client_credentials` trade it for one on first use through
Airbyte Cloud's ``POST {base_url}/applications/token`` grant.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.bi_catalog.airbyte_config import AirbyteConfig
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.shape_guard import ShapeGuard
from pirn.exceptions.connector_config_error import ConnectorConfigError


class AirbyteClient(ApiClient, TableSource):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: AirbyteConfig | None = None,
        *,
        client: Any = None,
        resource: str = "connections",
    ) -> None:
        if config is None and client is None:
            raise TypeError("AirbyteClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError("AirbyteClient: resource must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AirbyteConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    async def list_connections(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Airbyte connections."""
        return await self._list_resource("connections", cursor=cursor, limit=limit)

    async def list_workspaces(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Airbyte workspaces."""
        return await self._list_resource("workspaces", cursor=cursor, limit=limit)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured resource."""
        return await self._list_resource(self._resource, cursor=cursor, limit=page_size)

    async def _list_resource(
        self,
        resource: str,
        *,
        cursor: str | None,
        limit: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        body: dict[str, Any] = {}
        if limit is not None:
            body["limit"] = limit
        if cursor is not None:
            body["cursor"] = cursor
        response = await self.request(
            "POST",
            f"/v1/{resource}/list",
            body=body or None,
        )
        rows: list[Mapping[str, Any]] = list(response.get("data") or [])
        next_cursor = response.get("next_cursor")
        return rows, next_cursor if next_cursor else None

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
            client: Any = self._client
            if callable(getattr(client, "aclose", None)):
                await client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("airbyte.close")

    def _full_url(self, path: str) -> str:
        base = self._config.base_url if self._config is not None else ""
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _create_client(self) -> Any:
        if self._config is None:
            raise self._missing_config_error("AirbyteClient", "client")
        client = self._build_httpx_client("airbyte", scrub_errors=True)
        token = self._config.access_token
        if token is None:
            token = await self._exchange_client_credentials(client)
        # Set on the built client rather than passed to the builder: the same
        # pooled client performs the token exchange (unauthenticated, as the
        # grant requires) and then every authenticated call after it.
        client.headers["Authorization"] = f"Bearer {token}"
        self._logger.debug("airbyte.connect")
        return client

    async def _exchange_client_credentials(self, client: Any) -> str:
        """Exchange ``client_id`` / ``client_secret`` for a bearer token.

        Airbyte Cloud's OAuth2 client-credentials grant: ``POST
        {base_url}/applications/token`` returns an ``access_token`` valid for
        the lifetime of this connector. The token is held in memory only — it is
        never written back onto the frozen config, so ``close()``'s credential
        scrub still drops every secret this client held.

        There is no refresh: the grant is a fresh exchange, and a connector that
        outlives its token rebuilds its client (or is handed a longer-lived
        ``access_token`` directly).

        Args:
            client: The pooled client, before its ``Authorization`` header is
                set — the grant must be sent unauthenticated.

        Returns:
            The bearer token the API expects.

        Raises:
            ConnectorConfigError: If neither an ``access_token`` nor both halves
                of the client-credentials pair are configured, or the exchange
                returned no usable token.
        """
        config = self._config
        if config is None or config.client_id is None or config.client_secret is None:
            raise ConnectorConfigError(
                "AirbyteClient: config.access_token, or both config.client_id and "
                "config.client_secret to exchange for one, is required"
            )
        try:
            response = await client.request(
                "POST",
                self._full_url("/applications/token"),
                json={
                    "grant_type": "client_credentials",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                },
            )
            payload: Any = response.json()
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        token = payload.get("access_token") if ShapeGuard.is_str_keyed_mapping(payload) else None
        if not isinstance(token, str) or not token:
            raise ConnectorConfigError(
                "AirbyteClient: the client-credentials exchange returned no "
                "'access_token'; check config.client_id and config.client_secret"
            )
        self._logger.debug("airbyte.token_exchange")
        return token
