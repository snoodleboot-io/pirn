"""Async ``ApiClient`` wrapper around the synchronous atlassian Jira SDK.

``atlassian.Jira`` is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow Jira calls.

The connector exposes:

1. **Vendor-typed methods** (:meth:`search`).
2. The :class:`TableSource` capability — ``fetch_page`` runs the
   constructor's ``jql`` and pages via Jira's offset cursor
   (``startAt`` + ``maxResults``).
3. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.jira_config import JiraConfig


class JiraClient(ApiClient, TableSource):
    """Concrete :class:`ApiClient` backed by ``atlassian-python-api``.

    The Jira SDK exposes ``client.get(path, params=...)``,
    ``client.post(path, data=...)``, ``client.put(path, data=...)`` and
    ``client.delete(path)``. The generic :meth:`request` multiplexes
    based on HTTP method.
    """

    def __init__(
        self,
        config: JiraConfig | None = None,
        *,
        client: Any = None,
        jql: str | None = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("JiraClient requires either config= or client=")
        if jql is not None and (not isinstance(jql, str) or not jql):
            raise ValueError("JiraClient: jql must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._jql = jql
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> JiraConfig | None:
        return self._config

    @property
    def jql(self) -> str | None:
        return self._jql

    async def search(
        self,
        jql: str,
        *,
        start_at: int = 0,
        max_results: int = 50,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed search — return ``(issues, next_cursor)``.

        ``next_cursor`` is ``str(start_at + max_results)`` if more rows
        remain, else ``None``.
        """
        if not isinstance(jql, str) or not jql:
            raise ValueError("JiraClient.search: jql must be a non-empty string")
        return await self._search(jql, start_at=start_at, max_results=max_results)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the constructor's ``jql``."""
        if self._jql is None:
            raise RuntimeError("JiraClient.fetch_page: no jql configured")
        start_at = int(cursor) if cursor else 0
        max_results = page_size or 50
        return await self._search(self._jql, start_at=start_at, max_results=max_results)

    async def _search(
        self,
        jql: str,
        *,
        start_at: int,
        max_results: int,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        response = await self.request(
            "GET",
            "/search",
            params={
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
            },
        )
        return self._extract_page(response, start_at, max_results)

    @staticmethod
    def _extract_page(
        response: Any,
        start_at: int,
        max_results: int,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        if not isinstance(response, Mapping):
            return [], None
        issues = list(response.get("issues") or ())
        total = response.get("total")
        response_start = response.get("startAt", start_at)
        response_max = response.get("maxResults", max_results)
        try:
            start_int = int(response_start)
            max_int = int(response_max)
        except (TypeError, ValueError):
            start_int = start_at
            max_int = max_results
        next_offset = start_int + max_int
        if isinstance(total, int) and next_offset < total:
            return issues, str(next_offset)
        return issues, None

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
        method_upper = method.upper()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None

        def _run() -> Any:
            if method_upper == "GET":
                return client.get(path, params=request_params)
            if method_upper == "POST":
                return client.post(path, data=request_body)
            if method_upper == "PUT":
                return client.put(path, data=request_body)
            if method_upper == "DELETE":
                return client.delete(path)
            raise ValueError(f"JiraClient: unsupported HTTP method {method!r}")

        try:
            return await asyncio.to_thread(_run)
        except ValueError:
            raise
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("jira.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("JiraClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from atlassian import Jira  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "JiraClient requires atlassian-python-api; install via `pip install pirn[jira]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("JiraClient: missing config and no injected client")

        kwargs: dict[str, Any] = {"cloud": self._config.cloud}
        if self._config.url is not None:
            kwargs["url"] = self._config.url
        if self._config.username is not None:
            kwargs["username"] = self._config.username
        if self._config.api_token is not None:
            kwargs["password"] = self._config.api_token

        try:
            client = await asyncio.to_thread(Jira, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("jira.connect")
        return client
