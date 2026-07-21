"""``HttpRequestTool`` — async HTTP fetch with SSRF guard, allowlist, and size cap.

The tool lazily imports ``httpx`` (the ``web`` extra) only when no client is
injected, so importing the module stays backend-free. An injectable client and
DNS resolver keep unit tests fully offline. Every request is vetted by
:meth:`~pirn_agents.tools.web._ssrf_guard.SsrfGuard.assert_public_host`, restricted to
``GET``/``HEAD``, and the response body is streamed and truncated at
``max_bytes`` to protect the context window.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.web._ssrf_guard import SsrfGuard
from pirn_agents.tools.web.vetted_endpoint import VettedEndpoint


class HttpRequestTool(BaseTool):
    """Fetch an http(s) URL safely and return its (truncated) body."""

    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = 1_000_000,
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        allow_private: bool = False,
        client: Any | None = None,
        resolver: Callable[[str], str | Sequence[str]] | None = None,
    ) -> None:
        """Configure the fetch policy and optional injected client/resolver.

        Args:
            allowed_hosts: Optional host allow-list; when set, other hosts are refused.
            max_bytes: Maximum number of response-body bytes read before truncation.
            timeout: Overall per-request timeout in seconds.
            connect_timeout: Connection-establishment timeout in seconds.
            allow_private: When ``True``, skip the private/loopback IP guard
                (opt-in for trusted internal endpoints only).
            client: An optional ``httpx.AsyncClient``-compatible client; when
                provided it is used as-is (and not closed) instead of creating one.
            resolver: Optional hostname→IP resolver forwarded to the SSRF guard.

        Raises:
            ValueError: If ``max_bytes`` is not positive.
        """
        if max_bytes <= 0:
            raise ValueError(f"http_request: max_bytes must be positive, got {max_bytes}")
        self._guard = SsrfGuard(
            allowed_hosts=allowed_hosts, allow_private=allow_private, resolver=resolver
        )
        self._max_bytes = max_bytes
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._client = client

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"http_request"``."""
        return "http_request"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Fetch an http(s) URL (GET/HEAD) and return its status and body text."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``url`` and optional ``method`` arguments."""
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The absolute http(s) URL to fetch."},
                "method": {
                    "type": "string",
                    "description": "HTTP method: GET (default) or HEAD.",
                    "enum": ["GET", "HEAD"],
                },
            },
            "required": ["url"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Fetch the URL and return its status, headers, and truncated body.

        Returns:
            ``{"url", "status", "headers", "text", "truncated"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``url`` is missing, the method is unsupported, or the
                SSRF/allowlist guard rejects the host.
            ImportError: If no client is injected and ``httpx`` is not installed.
        """
        self._require_mapping(self.name, arguments)
        url = self._string_argument(self.name, arguments, "url")
        method = str(arguments.get("method", "GET")).upper()
        if method not in ("GET", "HEAD"):
            raise ValueError(f"http_request: unsupported method {method!r} (use GET or HEAD)")
        endpoint = self._guard.assert_public_host(url)
        if self._client is not None:
            return await self._request(self._client, method, url, endpoint)
        httpx = _require("web", "httpx")
        timeout = httpx.Timeout(self._timeout, connect=self._connect_timeout)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._request(client, method, url, endpoint)

    async def _request(
        self, client: Any, method: str, url: str, endpoint: VettedEndpoint
    ) -> dict[str, Any]:
        """Stream the response through ``client`` and cap the body at ``max_bytes``.

        The request is pinned to ``endpoint``: handing the original URL back to the
        client would let it re-resolve and defeat the guard just performed (PIR-746).
        """
        chunks: list[bytes] = []
        total = 0
        truncated = False
        async with client.stream(
            method,
            endpoint.pinned_url(url),
            headers=endpoint.request_headers(),
            extensions=endpoint.request_extensions,
        ) as response:
            status = int(response.status_code)
            headers = {str(k).lower(): str(v) for k, v in dict(response.headers).items()}
            async for chunk in response.aiter_bytes():
                if total >= self._max_bytes:
                    truncated = True
                    break
                remaining = self._max_bytes - total
                chunks.append(chunk[:remaining])
                total += len(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
        body = b"".join(chunks).decode("utf-8", errors="replace")
        return {
            "url": url,
            "status": status,
            "headers": headers,
            "text": body,
            "truncated": truncated,
        }
