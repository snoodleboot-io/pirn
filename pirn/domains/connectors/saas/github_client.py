"""Async ``ApiClient`` wrapper around the synchronous PyGithub SDK.

PyGithub is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow GitHub calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.github_config import GitHubConfig


class GitHubClient(ApiClient):
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
    ) -> None:
        if config is None and client is None:
            raise TypeError("GitHubClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GitHubConfig | None:
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
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
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
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("github.connect")
        return client
