"""``HttpConnector`` — a pooled async HTTP/REST connector (F16-S1 / PIR-352).

A :class:`~pirn_agents.connector_base.ConnectorBase` subclass that wraps a
single pooled ``httpx.AsyncClient`` and reuses it across every request for the
whole run (the pooling lever, AD-3). On top of the F2 lifecycle it adds:

* ``CredentialRef``-based auth (bearer token or api-key header),
* a bounded retry policy with exponential backoff on transient errors and
  retryable status codes,
* streaming response bodies via :meth:`stream_bytes` (never buffers the payload),
* an **egress guard** applied to every request URL.

Egress seam (F11). The egress check is an injectable ``egress_policy`` callable
``(url) -> None`` that raises on a disallowed target. It defaults to the F6
SSRF/egress guard (:func:`~pirn_agents.tools.web._ssrf_guard.assert_public_host`,
which blocks private/loopback/link-local/reserved/multicast IPs and the cloud
metadata endpoint, with an optional host allow-list). F11's richer egress
*policy* slots in here later by passing ``egress_policy`` — no API change needed.

``httpx`` is imported lazily inside :meth:`_create_client`; an injected
``client`` keeps unit tests fully offline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.tools.web._ssrf_guard import assert_public_host


class HttpConnector(ConnectorBase):
    """Pooled async HTTP/REST client with auth, retries, and an egress guard."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        credential: CredentialRef | None = None,
        auth_scheme: str = "bearer",
        api_key_header: str = "X-API-Key",
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_retries: int = 2,
        backoff_base: float = 0.05,
        backoff_cap: float = 2.0,
        retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
        allowed_hosts: tuple[str, ...] | None = None,
        allow_private: bool = False,
        resolver: Callable[[str], str] | None = None,
        egress_policy: Callable[[str], None] | None = None,
        is_retryable_exception: Callable[[BaseException], bool] | None = None,
        sleep: Callable[[float], Any] | None = None,
        client: Any | None = None,
    ) -> None:
        """Configure the pooled client, auth, retry policy, and egress guard.

        Args:
            base_url: Optional base URL joined with relative request paths.
            credential: Optional :class:`CredentialRef` for auth (see ``auth_scheme``).
            auth_scheme: ``"bearer"``, ``"api_key"``, or ``"none"``.
            api_key_header: Header name used when ``auth_scheme == "api_key"``.
            timeout: Overall per-request timeout in seconds.
            connect_timeout: Connection-establishment timeout in seconds.
            max_retries: Maximum retries after the first attempt (>= 0).
            backoff_base: Base delay (seconds) for the exponential schedule.
            backoff_cap: Upper bound (seconds) on the exponential term.
            retry_statuses: Response status codes that trigger a retry.
            allowed_hosts: Optional host allow-list forwarded to the default guard.
            allow_private: When ``True``, the default guard skips the private-IP check.
            resolver: Optional hostname->IP resolver forwarded to the default guard.
            egress_policy: Optional ``(url) -> None`` egress check that raises on a
                disallowed target. Defaults to the F6 SSRF/egress guard; this is
                the seam where F11's richer egress policy slots in.
            is_retryable_exception: Predicate deciding whether a raised exception
                is retryable; defaults to retrying every exception.
            sleep: Awaitable sleep between attempts; defaults to ``asyncio.sleep``.
            client: An optional pre-built ``httpx.AsyncClient``-compatible client;
                when provided it is pooled as-is instead of building one lazily.

        Raises:
            TypeError: If ``credential`` is not a ``CredentialRef`` or ``None``.
            ValueError: If ``auth_scheme`` is unknown, ``max_retries`` is negative,
                or a timeout/backoff bound is not positive.
        """
        super().__init__(credential=credential)
        if auth_scheme not in ("bearer", "api_key", "none"):
            raise ValueError(
                f"HttpConnector: auth_scheme must be 'bearer'|'api_key'|'none', got {auth_scheme!r}"
            )
        if max_retries < 0:
            raise ValueError(f"HttpConnector: max_retries must be >= 0, got {max_retries}")
        if timeout <= 0 or connect_timeout <= 0:
            raise ValueError("HttpConnector: timeout and connect_timeout must be positive")
        if backoff_base <= 0 or backoff_cap <= 0:
            raise ValueError("HttpConnector: backoff_base and backoff_cap must be positive")
        self._base_url = base_url
        self._auth_scheme = auth_scheme
        self._api_key_header = api_key_header
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._retry_statuses = retry_statuses
        self._allowed_hosts = allowed_hosts
        self._allow_private = allow_private
        self._resolver = resolver
        self._egress_policy = egress_policy if egress_policy is not None else self._ssrf_egress
        self._is_retryable_exception = (
            is_retryable_exception if is_retryable_exception is not None else self._always_retry
        )
        self._sleep = sleep if sleep is not None else self._default_sleep
        if client is not None:
            self._client = client

    async def _create_client(self) -> Any:
        """Build the pooled ``httpx.AsyncClient`` lazily (the ``web`` extra)."""
        httpx = self._require("web", "httpx")
        timeout = httpx.Timeout(self._timeout, connect=self._connect_timeout)
        return httpx.AsyncClient(
            base_url=self._base_url or "", timeout=timeout, follow_redirects=False
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Send a request through the pooled client with auth, guard, and retries.

        Args:
            method: HTTP method (e.g. ``"GET"``).
            url: Absolute URL, or a path resolved against ``base_url``.
            headers: Optional headers merged over the auth headers.
            params: Optional query parameters.

        Returns:
            The backend response object (e.g. an ``httpx.Response``).

        Raises:
            ValueError: If the egress guard rejects the resolved URL.
        """
        target = self._absolute_url(url)
        self._egress_policy(target)
        client = await self._get_client()
        merged = self._auth_headers()
        if headers:
            merged.update(headers)
        attempt = 0
        while True:
            try:
                response = await client.request(method, url, headers=merged, params=params)
            except Exception as exc:
                if attempt >= self._max_retries or not self._is_retryable_exception(exc):
                    raise
                await self._sleep(self._delay_for(attempt))
                attempt += 1
                continue
            if response.status_code not in self._retry_statuses or attempt >= self._max_retries:
                return response
            await self._sleep(self._delay_for(attempt))
            attempt += 1

    async def stream_bytes(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield the response body chunk-by-chunk without buffering the payload.

        Args:
            method: HTTP method.
            url: Absolute URL, or a path resolved against ``base_url``.
            headers: Optional headers merged over the auth headers.
            params: Optional query parameters.

        Yields:
            Successive body byte chunks from the streamed response.

        Raises:
            ValueError: If the egress guard rejects the resolved URL.
        """
        target = self._absolute_url(url)
        self._egress_policy(target)
        client = await self._get_client()
        merged = self._auth_headers()
        if headers:
            merged.update(headers)
        async with client.stream(method, url, headers=merged, params=params) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

    def _auth_headers(self) -> dict[str, str]:
        """Build the auth headers for the configured scheme and credential."""
        if self._credential is None or self._auth_scheme == "none":
            return {}
        secret = self._credential.reveal()
        if self._auth_scheme == "bearer":
            return {"Authorization": f"Bearer {secret}"}
        return {self._api_key_header: secret}

    def _absolute_url(self, url: str) -> str:
        """Return an absolute URL, joining ``url`` onto ``base_url`` if relative."""
        if "://" in url or self._base_url is None:
            return url
        return f"{self._base_url.rstrip('/')}/{url.lstrip('/')}"

    def _delay_for(self, attempt: int) -> float:
        """Return the exponential backoff delay for a zero-based ``attempt``."""
        return min(self._backoff_cap, self._backoff_base * (2**attempt))

    def _ssrf_egress(self, url: str) -> None:
        """Default egress policy: the F6 SSRF/egress guard (the F11 seam)."""
        assert_public_host(
            url,
            allowed_hosts=self._allowed_hosts,
            allow_private=self._allow_private,
            resolver=self._resolver,
        )

    def _always_retry(self, _exc: BaseException) -> bool:
        """Default retry predicate: every raised exception is retryable."""
        return True

    async def _default_sleep(self, seconds: float) -> None:
        """Default inter-attempt sleep delegating to ``asyncio.sleep``."""
        import asyncio

        await asyncio.sleep(seconds)
