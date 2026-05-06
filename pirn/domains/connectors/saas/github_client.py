"""Async ``ApiClient`` wrapper around the synchronous PyGithub SDK.

PyGithub is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow GitHub calls.

The connector exposes:

1. **Vendor-typed methods** (:meth:`list_repos`, :meth:`list_issues`).
2. The :class:`TableSource` capability — ``fetch_page`` pages the
   configured ``resource`` (``issues`` by default) using GitHub's
   ``?page=N`` cursor.
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
from pirn.domains.connectors.saas.github_config import GitHubConfig


class GitHubClient(ApiClient, TableSource):
    """Concrete :class:`ApiClient` backed by PyGithub.

    The PyGithub ``Github`` instance exposes a ``requester`` whose
    ``requestJsonAndCheck(method, url, parameters, headers, input)`` is
    used for the generic :meth:`request` interface. Tests inject a stub
    ``Github``-shaped object via ``client=`` whose ``requester`` mirrors
    the same surface.
    """

    def __init__(
        self,
        config: GitHubConfig | None = None,
        *,
        client: Any = None,
        resource: str = "issues",
    ) -> None:
        if config is None and client is None:
            raise TypeError("GitHubClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError(
                "GitHubClient: resource must be a non-empty string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GitHubConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    async def list_repos(
        self,
        owner: str,
        *,
        page: int = 1,
        per_page: int = 30,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of repos for ``owner``.

        Returns ``(rows, next_cursor)``. ``next_cursor`` is the next page
        number as a string when the current page is full; ``None`` when
        the listing is exhausted.
        """
        if not isinstance(owner, str) or not owner:
            raise ValueError(
                "GitHubClient.list_repos: owner must be a non-empty string"
            )
        return await self._list_resource(
            f"/users/{owner}/repos", page=page, per_page=per_page
        )

    async def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        page: int = 1,
        per_page: int = 30,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of issues for ``owner/repo``."""
        if not isinstance(owner, str) or not owner:
            raise ValueError(
                "GitHubClient.list_issues: owner must be a non-empty string"
            )
        if not isinstance(repo, str) or not repo:
            raise ValueError(
                "GitHubClient.list_issues: repo must be a non-empty string"
            )
        return await self._list_resource(
            f"/repos/{owner}/{repo}/issues", page=page, per_page=per_page
        )

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages ``self.resource``.

        ``cursor`` encodes the GitHub page number. ``None`` starts at
        page 1. The ``next_cursor`` is the next page number as a string
        when the response is full (``len(rows) == page_size``); otherwise
        ``None`` to terminate the stream.
        """
        page = int(cursor) if cursor else 1
        per_page = page_size or 30
        return await self._list_resource(
            f"/{self._resource.lstrip('/')}",
            page=page,
            per_page=per_page,
        )

    async def _list_resource(
        self,
        path: str,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        response = await self.request("GET", path, params=params)
        rows = self._extract_rows(response)
        next_cursor = (
            str(page + 1) if rows and len(rows) == per_page else None
        )
        return rows, next_cursor

    @staticmethod
    def _extract_rows(response: Any) -> list[Mapping[str, Any]]:
        # PyGithub's ``requestJsonAndCheck`` returns ``(headers, body)``;
        # raw HTTP returns ``body`` directly. Handle both shapes.
        if isinstance(response, tuple) and len(response) == 2:
            body = response[1]
        else:
            body = response
        if isinstance(body, list):
            return list(body)
        return []

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
        request_params = dict(params) if params is not None else None
        request_headers = dict(headers) if headers is not None else None
        request_body = dict(body) if body is not None else None

        def _run() -> Any:
            requester = client.requester
            return requester.requestJsonAndCheck(
                method,
                path,
                request_params,
                request_headers,
                request_body,
            )

        try:
            return await asyncio.to_thread(_run)
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
        self._logger.debug("github.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("GitHubClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from github import Auth, Github  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "GitHubClient requires PyGithub; install via "
                "`pip install pirn[github]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "GitHubClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {"base_url": self._config.base_url}
        if self._config.token is not None:
            kwargs["auth"] = Auth.Token(self._config.token)
        elif (
            self._config.app_id is not None
            and self._config.private_key is not None
        ):
            kwargs["auth"] = Auth.AppAuth(
                self._config.app_id, self._config.private_key
            )

        try:
            client = await asyncio.to_thread(Github, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("github.connect")
        return client
