"""Salesforce SaaS connector wrapping the synchronous ``simple-salesforce`` SDK.

``simple-salesforce`` is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop. SOQL queries (``GET`` against a
``query`` path) are dispatched to ``Salesforce.query``; everything else
is sent through ``Salesforce.restful``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.salesforce_config import SalesforceConfig


class SalesforceClient(ApiClient):
    """Async wrapper over a sync ``simple_salesforce.Salesforce`` client."""

    def __init__(
        self,
        config: SalesforceConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "SalesforceClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> SalesforceConfig | None:
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
            raise ValueError("SalesforceClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("SalesforceClient.request: path must be non-empty")
        client = await self._ensure_client()
        upper_method = method.upper()

        def _run() -> Any:
            if upper_method == "GET" and self._is_soql_path(path):
                soql = self._extract_soql(path, params)
                return client.query(soql)
            return client.restful(
                path,
                method=upper_method,
                params=dict(params) if params is not None else None,
                json=dict(body) if body is not None else None,
            )

        return await asyncio.to_thread(_run)

    async def close(self) -> None:
        if self._client is not None:
            session = getattr(self._client, "session", None)
            close_fn = getattr(session, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._closed = True
        self._logger.debug("salesforce.close")

    @staticmethod
    def _is_soql_path(path: str) -> bool:
        normalised = path.lstrip("/").lower()
        return normalised.startswith("query") or normalised.endswith("/query")

    @staticmethod
    def _extract_soql(
        path: str, params: Mapping[str, Any] | None
    ) -> str:
        if params is not None and "q" in params:
            return str(params["q"])
        if "?" in path:
            _, _, query_string = path.partition("?")
            for pair in query_string.split("&"):
                key, sep, value = pair.partition("=")
                if sep and key.lower() == "q":
                    return value
        raise ValueError(
            "SalesforceClient.request: SOQL path requires 'q' parameter"
        )

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("SalesforceClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from simple_salesforce import Salesforce  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "SalesforceClient requires simple-salesforce; install via "
                "`pip install pirn[salesforce]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "SalesforceClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {"domain": self._config.domain}
        for name in (
            "username",
            "password",
            "security_token",
            "consumer_key",
            "consumer_secret",
        ):
            value = getattr(self._config, name)
            if value is not None:
                kwargs[name] = value
        try:
            client = await asyncio.to_thread(Salesforce, **kwargs)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("salesforce.connect")
        return client
