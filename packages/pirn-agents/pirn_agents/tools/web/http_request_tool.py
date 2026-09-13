"""``HttpRequestTool`` — async HTTP fetch with SSRF guard, allowlist, and size cap.

The tool lazily imports ``httpx`` (the ``web`` extra) only when no client is
bound, so importing the module stays backend-free. A bindable client and DNS
resolver keep unit tests fully offline. Every request is vetted by
:meth:`~pirn.security.ssrf_guard.SsrfGuard.assert_public_host`, restricted to
``GET``/``HEAD``, and the response body is streamed and truncated at
``max_bytes`` to protect the context window.

The fetch policy — ``allowed_hosts``, ``allow_private``, ``max_bytes``, the
timeouts, the injected ``client``/``resolver`` — is bound once with
``HttpRequestTool.bind(...)``; a call supplies ``url`` and ``method``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.security.ssrf_guard import SsrfGuard
from pirn.security.vetted_endpoint import VettedEndpoint
from pydantic import Field

from pirn_agents._internal._require import _require
from pirn_agents.tools.tool import Tool


class HttpRequestTool(Tool):
    """Fetch an http(s) URL (GET/HEAD) and return its status and body text."""

    tool_name: ClassVar[str] = "http_request"

    def __init__(
        self,
        *,
        url: Knot | str,
        method: Knot | str = "GET",
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = 1_000_000,
        timeout: Knot | float = 10.0,
        connect_timeout: Knot | float = 5.0,
        allow_private: Knot | bool = False,
        client: Any | None = None,
        resolver: Any | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            url=url,
            method=method,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            timeout=timeout,
            connect_timeout=connect_timeout,
            allow_private=allow_private,
            client=client,
            resolver=resolver,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        url: Annotated[str, Field(description="The absolute http(s) URL to fetch.")],
        method: Annotated[
            Literal["GET", "HEAD"], Field(description="HTTP method: GET (default) or HEAD.")
        ] = "GET",
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = 1_000_000,
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        allow_private: bool = False,
        # ``client`` / ``resolver`` are typed ``Any``: an ``httpx.AsyncClient``
        # and a bare callable have no pydantic schema for core's eager adapter
        # build, and both are bound policy, never model-supplied.
        client: Any = None,
        resolver: Any = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Fetch the URL and return its status, headers, and truncated body.

        Args:
            url: The absolute http(s) URL to fetch.
            method: ``GET`` (default) or ``HEAD``.
            allowed_hosts: Optional host allow-list; other hosts are refused.
            max_bytes: Maximum number of response-body bytes read before truncation.
            timeout: Overall per-request timeout in seconds.
            connect_timeout: Connection-establishment timeout in seconds.
            allow_private: When ``True``, skip the private/loopback IP guard
                (opt-in for trusted internal endpoints only).
            client: An optional ``httpx.AsyncClient``-compatible client; when
                bound it is used as-is (and not closed) instead of creating one.
            resolver: Optional hostname->IP resolver forwarded to the SSRF guard.

        Returns:
            ``{"url", "status", "headers", "text", "truncated"}``.

        Raises:
            ValueError: If ``max_bytes`` is not positive, ``url`` is empty, the
                method is unsupported, or the SSRF/allowlist guard rejects the host.
            ImportError: If no client is bound and ``httpx`` is not installed.
        """
        if max_bytes <= 0:
            raise ValueError(f"http_request: max_bytes must be positive, got {max_bytes}")
        if not url:
            raise ValueError("http_request: 'url' must be a non-empty string")
        verb = str(method).upper()
        if verb not in ("GET", "HEAD"):
            raise ValueError(f"http_request: unsupported method {method!r} (use GET or HEAD)")
        guard = SsrfGuard(
            allowed_hosts=allowed_hosts, allow_private=allow_private, resolver=resolver
        )
        endpoint = guard.assert_public_host(url)
        if client is not None:
            return await self._request(client, verb, url, endpoint, max_bytes)
        httpx = _require("web", "httpx")
        limits = httpx.Timeout(timeout, connect=connect_timeout)
        async with httpx.AsyncClient(timeout=limits, follow_redirects=False) as own_client:
            return await self._request(own_client, verb, url, endpoint, max_bytes)

    @staticmethod
    async def _request(
        client: Any, method: str, url: str, endpoint: VettedEndpoint, max_bytes: int
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
                if total >= max_bytes:
                    truncated = True
                    break
                remaining = max_bytes - total
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
