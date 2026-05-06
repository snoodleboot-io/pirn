"""Salesforce SaaS connector wrapping the synchronous ``simple-salesforce`` SDK.

``simple-salesforce`` is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop. SOQL queries (``GET`` against a
``query`` path) are dispatched to ``Salesforce.query``; everything else
is sent through ``Salesforce.restful``.

The connector exposes:

1. **Vendor-typed methods** for SOQL streaming (:meth:`soql`).
2. The :class:`TableSource` capability — ``fetch_page`` runs the
   constructor's ``soql_query`` and pages via Salesforce's
   ``nextRecordsUrl`` cursor.
3. The :class:`RecordWriter` capability — ``write_records`` posts each
   record to ``/sobjects/<sobject_type>``. The ``sobject_type`` defaults
   to ``"Account"`` if not supplied at construction.
4. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable, Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.salesforce_config import SalesforceConfig


class SalesforceClient(ApiClient, TableSource, RecordWriter):
    """Async wrapper over a sync ``simple_salesforce.Salesforce`` client."""

    def __init__(
        self,
        config: SalesforceConfig | None = None,
        *,
        client: Any = None,
        soql_query: str | None = None,
        sobject_type: str | None = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "SalesforceClient requires either config= or client="
            )
        if soql_query is not None and (
            not isinstance(soql_query, str) or not soql_query
        ):
            raise ValueError(
                "SalesforceClient: soql_query must be a non-empty string"
            )
        if sobject_type is not None and (
            not isinstance(sobject_type, str) or not sobject_type
        ):
            raise ValueError(
                "SalesforceClient: sobject_type must be a non-empty string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._soql_query = soql_query
        self._sobject_type = sobject_type or "Account"
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> SalesforceConfig | None:
        return self._config

    @property
    def soql_query(self) -> str | None:
        return self._soql_query

    @property
    def sobject_type(self) -> str:
        return self._sobject_type

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages a SOQL query.

        Salesforce pagination is URL-driven: when ``done=False`` the
        response includes a ``nextRecordsUrl``; we expose that string as
        the cursor and re-issue a ``GET`` against it on the next call.
        Salesforce ignores ``page_size`` for SOQL responses (the server
        chooses the batch size), so the parameter is accepted for
        capability conformance and not forwarded.
        """
        del page_size  # SOQL batch size is server-controlled.
        if cursor is not None:
            response = await self.request("GET", cursor)
        else:
            if self._soql_query is None:
                raise RuntimeError(
                    "SalesforceClient.fetch_page: no soql_query configured "
                    "and no cursor supplied"
                )
            response = await self.request(
                "GET", "/query", params={"q": self._soql_query}
            )
        return self._extract_page(response)

    async def soql(
        self,
        query: str,
        *,
        batch_size: int = 200,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Vendor-typed helper — yield every row from a SOQL query.

        Internally pages over Salesforce's ``nextRecordsUrl`` cursor.
        ``batch_size`` is accepted for API parity but Salesforce chooses
        the server-side batch size; we honour whatever it returns.
        """
        del batch_size  # Salesforce controls SOQL batch size server-side.
        if not isinstance(query, str) or not query:
            raise ValueError(
                "SalesforceClient.soql: query must be a non-empty string"
            )
        response = await self.request("GET", "/query", params={"q": query})
        rows, cursor = self._extract_page(response)
        for row in rows:
            yield row
        while cursor is not None:
            response = await self.request("GET", cursor)
            rows, cursor = self._extract_page(response)
            for row in rows:
                yield row

    async def write_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> int:
        """Persist ``records`` as ``sobject_type`` rows; return the count.

        Each record is POSTed to ``/sobjects/<sobject_type>``. The
        ``sobject_type`` is fixed at construction time and defaults to
        ``"Account"`` when not supplied.
        """
        materialised = list(records)
        path = f"/sobjects/{self._sobject_type}"
        for record in materialised:
            await self.request("POST", path, body=record)
        return len(materialised)

    @staticmethod
    def _extract_page(
        response: Any,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        if not isinstance(response, Mapping):
            return [], None
        rows = list(response.get("records") or ())
        done = bool(response.get("done", True))
        next_url = response.get("nextRecordsUrl")
        next_cursor = (
            str(next_url) if (not done and next_url) else None
        )
        return rows, next_cursor

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
        self._clear_credentials()
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
            self._reraise_scrubbed(exc)
        self._logger.debug("salesforce.connect")
        return client
