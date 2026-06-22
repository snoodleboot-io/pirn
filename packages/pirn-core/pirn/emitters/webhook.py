"""Webhook emitter — POST run events to configured HTTP endpoints."""

from __future__ import annotations

import ipaddress
import urllib.parse
from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent


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
        """Initialise the emitter.

        Args:
            client: A pre-created ``httpx.AsyncClient``.  When provided,
                ``timeout_seconds``, ``verify``, and ``ssl_context`` are
                ignored.
            url_status: URL to POST status events to.  ``None`` disables
                status delivery.
            url_lineage: URL to POST lineage records to.  ``None``
                disables lineage delivery.
            url_result: URL to POST run results to.  ``None`` disables
                result delivery.
            timeout_seconds: Per-request timeout in seconds.  Defaults
                to ``5.0``.
            verify: TLS verification argument forwarded to
                ``httpx.AsyncClient``.  ``True`` (default) verifies
                against system CAs; ``False`` disables verification
                entirely — **never use in production**; a path string
                is treated as a CA-bundle PEM file.
            ssl_context: An ``ssl.SSLContext`` instance.  When provided
                it takes precedence over ``verify``.
            block_private_ips: When ``True``, any URL that resolves at
                construction time to a private, loopback, or link-local
                IP address is rejected with ``ValueError``.  Defaults
                to ``False``.

        Raises:
            ValueError: If a URL uses a non-http/https scheme, or if
                ``block_private_ips=True`` and a URL resolves to a
                private IP.
        """
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
                    self.__check_url_for_ssrf(url)
                else:
                    self.__check_url_scheme(url)

    @staticmethod
    def __check_url_for_ssrf(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"WebhookEmitter: URL scheme {parsed.scheme!r} is not permitted; use http or https"
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

    @staticmethod
    def __check_url_scheme(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"WebhookEmitter: URL scheme {parsed.scheme!r} is not permitted; use http or https"
            )

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
        """POST a JSON payload string to a URL with ``Content-Type: application/json``.

        Args:
            url: Target URL.
            payload: JSON-encoded string body.
        """
        client = await self._ensure_client()
        await client.post(
            url,
            content=payload,
            headers={"Content-Type": "application/json"},
        )

    async def on_status(self, event: StatusEvent) -> None:
        """POSTs a JSON-serialised status event to the configured URL.

        Does nothing when no status URL was configured.

        Args:
            event: The status event to deliver.
        """
        if self._url_status is None:
            return
        await self._post(self._url_status, event.model_dump_json())

    async def on_lineage(self, record: KnotLineage) -> None:
        """POSTs a JSON-serialised lineage record to the configured URL.

        Does nothing when no lineage URL was configured.

        Args:
            record: The knot lineage record to deliver.
        """
        if self._url_lineage is None:
            return
        await self._post(self._url_lineage, record.model_dump_json())

    async def on_run_result(self, result: RunResult) -> None:
        """POSTs a JSON-serialised run result to the configured URL.

        Does nothing when no result URL was configured.

        Args:
            result: The completed run result to deliver.
        """
        if self._url_result is None:
            return
        await self._post(self._url_result, result.model_dump_json())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
