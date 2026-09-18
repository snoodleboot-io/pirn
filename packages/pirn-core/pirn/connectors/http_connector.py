"""``HttpConnector`` — a pooled async HTTP/REST connector (F16-S1 / PIR-352).

A :class:`~pirn.connectors.connector_base.ConnectorBase` subclass that wraps a
single pooled ``httpx.AsyncClient`` and reuses it across every request for the
whole run (the pooling lever, AD-3). On top of the F2 lifecycle it adds:

* ``CredentialRef``-based auth (bearer token or api-key header),
* retries scheduled by :class:`~pirn.core.knot_retry_policy.KnotRetryPolicy`
  (see "Retries" below),
* streaming response bodies via :meth:`stream_bytes` (never buffers the payload),
* an **egress guard** applied to every request URL.

Retries. There is no retry loop here: one call to :meth:`request` performs one
attempt, and :meth:`~pirn.core.knot_retry_policy.KnotRetryPolicy.run` decides
whether to run another. That is the same jittered, capped, ``Retry-After``-aware
schedule the engine applies to a knot dispatch, so a request made below the knot
boundary and a knot dispatch back off identically instead of this module carrying
a second implementation.

Two rules narrow what the schedule will repeat:

* **Only an idempotent method is retried.** ``POST`` and ``PATCH`` are not:
  re-sending one after a timeout can duplicate a side effect the server already
  applied, and the client cannot tell a lost request from a lost response.
  ``idempotent_methods`` names the set (RFC 9110 §9.2.2 by default).
* **Only a transient failure is retried.** The default predicate accepts a
  retryable status (raised as
  :class:`~pirn.exceptions.http_retryable_status_error.HttpRetryableStatusError`)
  and an ``httpx.TransportError`` — a connect/read timeout, a dropped
  connection, a protocol error. A ``ValueError`` from the egress guard or a
  programming error in a response handler is not transient and propagates on the
  first attempt.

A retryable status that outlives the retry budget is **returned, not raised**: a
``429`` or ``503`` is a response the caller may want to inspect, and the
pre-``KnotRetryPolicy`` connector returned it too.

Egress seam (F11). The egress check is an injectable ``egress_policy`` callable
``(url) -> VettedEndpoint`` that raises on a disallowed target. It defaults to the
F6 SSRF/egress guard
(:meth:`~pirn.security.ssrf_guard.SsrfGuard.assert_public_host`, which
blocks private/loopback/link-local/reserved/multicast IPs and the cloud metadata
endpoint, with an optional host allow-list).

**The policy must return a** ``VettedEndpoint``, and that is what keeps DNS
rebinding closed: the request is pinned to the address the policy vetted, so the
HTTP client never re-resolves the hostname and there is no second lookup for a
short-TTL attacker record to poison. The type forbids returning nothing, so a
request can never silently skip pinning. Compose
:class:`~pirn.security.egress_policy.EgressPolicy`, which returns the
endpoint.

``httpx`` is imported lazily inside :meth:`_create_client`; an injected
``client`` keeps unit tests fully offline. Note that ``follow_redirects=False`` is
a **security invariant**, not hygiene: a followed redirect would have the client
resolve the ``Location`` host itself, defeating the pin. Clients this module
constructs set it; an injected client must too.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from functools import partial
from typing import Any

from pirn.connectors.connector_base import ConnectorBase
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.optional_dependency import OptionalDependency
from pirn.exceptions.http_retryable_status_error import HttpRetryableStatusError
from pirn.security.credential_ref import CredentialRef
from pirn.security.ssrf_guard import SsrfGuard
from pirn.security.vetted_endpoint import VettedEndpoint


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
        retry: KnotRetryPolicy | None = None,
        retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
        idempotent_methods: tuple[str, ...] = (
            "GET",
            "HEAD",
            "OPTIONS",
            "TRACE",
            "PUT",
            "DELETE",
        ),
        allowed_hosts: tuple[str, ...] | None = None,
        allow_private: bool = False,
        resolver: Callable[[str], str | Sequence[str]] | None = None,
        egress_policy: Callable[[str], VettedEndpoint] | None = None,
        is_retryable_exception: Callable[[BaseException], bool] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
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
            retry: The schedule :meth:`request` retries on, the same
                :class:`~pirn.core.knot_retry_policy.KnotRetryPolicy` type the
                engine applies to a knot dispatch. Defaults to three attempts
                with the policy's own jittered, capped exponential backoff.
                ``KnotRetryPolicy(max_attempts=1)`` disables retrying.
            retry_statuses: Response status codes treated as transient. An
                attempt that returns one raises
                :class:`~pirn.exceptions.http_retryable_status_error.HttpRetryableStatusError`
                so ``retry`` schedules another; the response is returned once
                the budget is spent.
            idempotent_methods: Uppercase methods safe to re-send. A method
                outside this set is attempted exactly once however transient the
                failure looks, because a retry could duplicate a side effect the
                server already applied.
            allowed_hosts: Optional host allow-list forwarded to the default guard.
            allow_private: When ``True``, the default guard skips the private-IP check.
            resolver: Optional hostname->IP resolver forwarded to the default guard.
            egress_policy: Optional ``(url) -> VettedEndpoint`` egress check that
                raises on a disallowed target and returns the vetted endpoint the
                request is pinned to (returning nothing is a type error, so pinning
                can never be silently skipped). Defaults to the F6 SSRF/egress
                guard; this is the seam where F11's richer egress policy slots in.
            is_retryable_exception: Predicate deciding whether a raised exception
                is transient. Defaults to a retryable status or an
                ``httpx.TransportError``; every other exception propagates from
                the first attempt.
            sleep: Awaitable sleep between attempts; defaults to ``asyncio.sleep``.
            client: An optional pre-built ``httpx.AsyncClient``-compatible client;
                when provided it is pooled as-is instead of building one lazily.

        Raises:
            TypeError: If ``credential`` is not a ``CredentialRef`` or ``None``,
                or ``retry`` is not a ``KnotRetryPolicy``.
            ValueError: If ``auth_scheme`` is unknown or a timeout is not positive.
        """
        super().__init__(credential=credential)
        if auth_scheme not in ("bearer", "api_key", "none"):
            raise ValueError(
                f"HttpConnector: auth_scheme must be 'bearer'|'api_key'|'none', got {auth_scheme!r}"
            )
        if retry is not None and not isinstance(retry, KnotRetryPolicy):
            raise TypeError(
                f"HttpConnector: retry must be a KnotRetryPolicy or None, got {type(retry).__name__}"
            )
        if timeout <= 0 or connect_timeout <= 0:
            raise ValueError("HttpConnector: timeout and connect_timeout must be positive")
        self._base_url = base_url
        self._auth_scheme = auth_scheme
        self._api_key_header = api_key_header
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._retry = retry if retry is not None else KnotRetryPolicy(max_attempts=3)
        self._retry_statuses = retry_statuses
        self._idempotent_methods = tuple(method.upper() for method in idempotent_methods)
        self._ssrf = SsrfGuard(
            allowed_hosts=allowed_hosts, allow_private=allow_private, resolver=resolver
        )
        self._egress_policy = egress_policy if egress_policy is not None else self._ssrf_egress
        self._is_retryable_exception = (
            is_retryable_exception if is_retryable_exception is not None else self._is_transient
        )
        self._sleep = sleep
        if client is not None:
            self._client = client

    async def _create_client(self) -> Any:
        """Build the pooled ``httpx.AsyncClient`` lazily (core's ``http`` extra)."""
        httpx = OptionalDependency.require("httpx", extra="http")
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

        One attempt is performed by :meth:`_attempt`; whether another follows is
        :meth:`~pirn.core.knot_retry_policy.KnotRetryPolicy.run`'s decision, and
        only for an idempotent *method* that failed transiently. A retryable
        status that survives the budget is returned rather than raised.

        Args:
            method: HTTP method (e.g. ``"GET"``).
            url: Absolute URL, or a path resolved against ``base_url``.
            headers: Optional headers merged over the auth headers.
            params: Optional query parameters. Note httpx replaces any query
                already present in the URL rather than merging with it.

        Returns:
            The backend response object (e.g. an ``httpx.Response``).

        Raises:
            ValueError: If the egress guard rejects the resolved URL.
        """
        target = self._absolute_url(url)
        endpoint = self._egress_policy(target)
        client = await self._get_client()
        merged = self._auth_headers()
        if headers:
            merged.update(headers)
        # Fetch `target`, not the raw `url` argument: the guard vetted `target`, and
        # sending anything else would mean checking one URL and requesting another.
        request_url, pinned_headers, extensions = self._pin(target, endpoint, merged)
        idempotent = method.upper() in self._idempotent_methods
        try:
            return await self._retry.run(
                partial(
                    self._attempt, client, method, request_url, pinned_headers, params, extensions
                ),
                call_id=f"HttpConnector.request:{method.upper()}",
                retry_on=partial(self._should_retry, idempotent),
                retry_after_hint=self._retry_after_seconds,
                sleep=self._sleep,
            )
        except HttpRetryableStatusError as spent:
            # The budget ran out on a status, not a failure: a 429 or 503 is a
            # response the caller may want to read, and raising here would make
            # an exhausted retry look different from a status never retried.
            return spent.response

    async def _attempt(
        self,
        client: Any,
        method: str,
        request_url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any] | None,
        extensions: Mapping[str, Any],
    ) -> Any:
        """Perform exactly one request; raise on a retryable status so the policy sees it."""
        response = await client.request(
            method,
            request_url,
            headers=headers,
            params=params,
            extensions=extensions,
        )
        status = int(response.status_code)
        if status in self._retry_statuses:
            raise HttpRetryableStatusError(response, status)
        return response

    def _should_retry(self, idempotent: bool, exc: Exception) -> bool:
        """Whether ``exc`` may be retried at all: idempotent method and transient cause."""
        return idempotent and self._is_retryable_exception(exc)

    def _is_transient(self, exc: BaseException) -> bool:
        """Default transience predicate: a retryable status or an httpx transport error.

        ``httpx`` is looked up in :data:`sys.modules` rather than imported: an
        exception of its type cannot exist unless the module is already loaded,
        and importing it here would defeat the lazy-backend rule.
        """
        if isinstance(exc, HttpRetryableStatusError):
            return True
        httpx = sys.modules.get("httpx")
        if httpx is None:
            return False
        transport_error: type[BaseException] = httpx.TransportError
        return isinstance(exc, transport_error)

    def _retry_after_seconds(self, exc: Exception) -> float | None:
        """Read a ``Retry-After`` delay (delta-seconds) off a retryable status response.

        Only the integer-seconds form is honoured; the HTTP-date form and any
        unparsable value yield ``None`` so the policy falls back to its own
        backoff. The policy caps whatever comes back with ``max_retry_after``,
        so a hostile header cannot park a run.
        """
        if not isinstance(exc, HttpRetryableStatusError):
            return None
        headers: Any = getattr(exc.response, "headers", None)
        if headers is None:
            return None
        raw: Any = headers.get("Retry-After") or headers.get("retry-after")
        if not isinstance(raw, str):
            return None
        try:
            seconds = float(raw.strip())
        except ValueError:
            return None
        return seconds if seconds >= 0 else None

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
            params: Optional query parameters. Note httpx replaces any query
                already present in the URL rather than merging with it.

        Yields:
            Successive body byte chunks from the streamed response.

        Raises:
            ValueError: If the egress guard rejects the resolved URL.
        """
        target = self._absolute_url(url)
        endpoint = self._egress_policy(target)
        client = await self._get_client()
        merged = self._auth_headers()
        if headers:
            merged.update(headers)
        request_url, pinned_headers, extensions = self._pin(target, endpoint, merged)
        async with client.stream(
            method, request_url, headers=pinned_headers, params=params, extensions=extensions
        ) as response:
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

    def _ssrf_egress(self, url: str) -> VettedEndpoint:
        """Default egress policy: the F6 SSRF/egress guard (the F11 seam)."""
        return self._ssrf.assert_public_host(url)

    def _pin(
        self, target: str, endpoint: VettedEndpoint, headers: dict[str, str]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Rewrite the request to the vetted address the egress policy returned.

        Re-resolving at connect time is what makes DNS rebinding possible, so the
        request goes to the address the guard actually checked, with the original
        hostname restored via ``Host`` and TLS SNI (PIR-746). The egress policy must
        return a :class:`VettedEndpoint` — not returning one is a type error, so a
        request can never silently skip pinning.
        """
        return (
            endpoint.pinned_url(target),
            endpoint.request_headers(headers),
            dict(endpoint.request_extensions),
        )
