"""Webhook emitter — POST run events to configured HTTP endpoints."""

from __future__ import annotations

import ipaddress
import urllib.parse
from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status_event import StatusEvent


def _check_url_for_ssrf(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/loopback address."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"WebhookEmitter: URL scheme {parsed.scheme!r} is not permitted; "
            "use http or https"
        )
    host = parsed.hostname
    if host is None:
        raise ValueError(f"WebhookEmitter: could not parse hostname from URL {url!r}")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError(
                f"WebhookEmitter: URL {url!r} resolves to a private/loopback address "
                f"({addr}); set block_private_ips=False to allow this"
            )
    except ValueError as exc:
        if "private" in str(exc) or "loopback" in str(exc):
            raise
        # Not an IP address — hostname; skip IP check (DNS resolution at
        # construction time would be too expensive and may not be stable)
        pass


def _check_url_scheme(url: str) -> None:
    """Raise ValueError if the URL scheme is not http or https."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"WebhookEmitter: URL scheme {parsed.scheme!r} is not permitted; "
            "use http or https"
        )


class WebhookEmitter(Emitter):
    """POSTs each event as JSON to one or more URLs.

    Per-event-type URLs are independent; pass ``None`` for any event
    type you don't care about.

    Construction:

    * ``WebhookEmitter(client=<httpx.AsyncClient>, ...)`` — inject a
      client (tests, custom timeouts, auth).
    * ``WebhookEmitter(url_status="...", ...)`` — build a client
      lazily.

    TLS options:

    * ``verify`` — passed directly to ``httpx.AsyncClient``.  Accepts
      ``True`` (default, verifies against system CAs), ``False``
      (disables verification — **never use in production**), or a path
      to a CA-bundle PEM file.
    * ``ssl_context`` — an ``ssl.SSLContext`` instance; when provided
      it takes precedence over ``verify``.

    Warning: never set ``verify=False`` in production — it disables TLS certificate
    verification entirely, exposing webhook traffic to man-in-the-middle attacks.
    To use a custom CA bundle, pass ``verify="/path/to/ca-bundle.pem"`` or an
    ``ssl.SSLContext`` via ``ssl_context=``.

    SSRF guard:

    * ``block_private_ips`` — when ``True``, URLs that resolve to a
      private, loopback, or link-local IP address are rejected at
      construction time.  Hostname-based URLs are not resolved at
      construction time.  Defaults to ``False``.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        url_status: str | None = None,
        url_lineage: str | None = None,
        url_result: str | None = None,
        timeout_seconds: float = 5.0,
        verify: bool | str = True,
        ssl_context: Any = None,
        block_private_ips: bool = False,
    ) -> None:
        self._client = client
        self._url_status = url_status
        self._url_lineage = url_lineage
        self._url_result = url_result
        self._timeout = timeout_seconds
        self._verify = verify
        self._ssl_context = ssl_context

        for url in (url_status, url_lineage, url_result):
            if url is not None:
                if block_private_ips:
                    _check_url_for_ssrf(url)
                else:
                    _check_url_scheme(url)

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:
                raise ImportError(
                    "WebhookEmitter requires httpx; install via `pip install pirn[http]`"
                ) from exc
            kwargs: dict[str, Any] = {"timeout": self._timeout, "verify": self._verify}
            if self._ssl_context is not None:
                kwargs["verify"] = self._ssl_context
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def _post(self, url: str, payload: str) -> None:
        client = await self._ensure_client()
        await client.post(
            url,
            content=payload,
            headers={"Content-Type": "application/json"},
        )

    async def on_status(self, event: StatusEvent) -> None:
        if self._url_status is None:
            return
        await self._post(self._url_status, event.model_dump_json())

    async def on_lineage(self, record: KnotLineage) -> None:
        if self._url_lineage is None:
            return
        await self._post(self._url_lineage, record.model_dump_json())

    async def on_run_result(self, result: RunResult) -> None:
        if self._url_result is None:
            return
        await self._post(self._url_result, result.model_dump_json())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
