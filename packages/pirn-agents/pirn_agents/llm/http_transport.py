"""``HttpTransport`` — the retry/POST/429 transport for HTTP LLM providers.

Extracted from ``BaseLLMProvider`` so the request-sending responsibility lives
in one focused collaborator (SRP): given a ready client, URL, headers, and JSON
payload it performs a single POST, classifies the HTTP status into typed errors,
and retries transient failures with jittered exponential backoff — honouring a
server ``Retry-After`` on HTTP 429. It owns no provider-specific shaping and
never imports a backend: transient transport errors are recognised by module +
class name so ``import pirn_agents`` stays ``httpx``-free.

Security: this transport never interpolates request headers or credentials into
any raised error message — errors carry only the HTTP status code or the
transport exception's own string, so an API key can never leak through an error
surfaced to a caller or log.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pirn.core.knot_retry_policy import KnotRetryPolicy

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.transient_llm_error import TransientLLMError


class HttpTransport:
    """Sends one POST with typed-error classification and backoff retries."""

    def __init__(
        self,
        *,
        retry_policy: KnotRetryPolicy,
        sleeper: Callable[[float], Awaitable[None]],
        rng: Callable[[], float] | None,
    ) -> None:
        """Initialise the transport with its retry/backoff dependencies.

        Args:
            retry_policy: Retry/backoff policy governing attempt count and delays.
            sleeper: Async sleep function used between retries (injected in tests).
            rng: Optional jitter source returning a float in ``[0, 1)``; ``None``
                defers to the policy's own :func:`random.random`.
        """
        self._retry_policy: KnotRetryPolicy = retry_policy
        self._sleep: Callable[[float], Awaitable[None]] = sleeper
        self._rng: Callable[[], float] | None = rng

    @property
    def retry_policy(self) -> KnotRetryPolicy:
        """Return the retry/backoff policy this transport applies."""
        return self._retry_policy

    @property
    def sleeper(self) -> Callable[[float], Awaitable[None]]:
        """Return the async sleep function awaited between retries."""
        return self._sleep

    @property
    def rng(self) -> Callable[[], float] | None:
        """Return the jitter source, or ``None`` for the policy's default."""
        return self._rng

    async def request_with_retries(
        self,
        *,
        client: Any,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> Any:
        """POST ``payload`` with jittered-backoff retries and 429 handling.

        Retries HTTP 429 (honouring ``Retry-After`` when present) and transient
        5xx/network errors until the policy's ``max_attempts`` are spent;
        propagates non-retryable errors immediately. The retry loop itself is
        core's :meth:`~pirn.core.knot_retry_policy.KnotRetryPolicy.run`; this
        method supplies only what is transport-specific: which exceptions are
        retryable, and the ``Retry-After`` hint.
        """
        return await self._retry_policy.run(
            functools.partial(
                self._post_json, client=client, url=url, headers=headers, payload=payload
            ),
            call_id="llm_http_post",
            retry_on=self._is_retryable,
            retry_after_hint=self._retry_after_of,
            sleep=self._sleep,
            rng=self._rng,
        )

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Whether a failed POST may be retried: a 429 or a transient error."""
        return isinstance(exc, (RateLimitError, TransientLLMError))

    @staticmethod
    def _retry_after_of(exc: Exception) -> float | None:
        """The server's ``Retry-After`` hint carried by a 429, if any."""
        return exc.retry_after if isinstance(exc, RateLimitError) else None

    async def _post_json(
        self,
        *,
        client: Any,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> Any:
        """Perform one POST and return parsed JSON, mapping errors to types.

        Maps status codes to typed errors: ``429`` → ``RateLimitError``;
        ``5xx`` → ``TransientLLMError``; other non-2xx → ``LLMHTTPStatusError``.
        Transport-level exceptions (timeouts, resets) become
        ``TransientLLMError`` so they retry. Error messages never include the
        request headers, so credentials cannot leak.
        """
        try:
            response = await client.post(url, json=dict(payload), headers=dict(headers))
        except Exception as exc:
            if isinstance(exc, (RateLimitError, TransientLLMError, LLMHTTPStatusError)):
                raise
            if self._is_transient_transport_error(exc):
                raise TransientLLMError(str(exc)) from exc
            raise
        status = int(response.status_code)
        if status == 429:
            raise RateLimitError("provider returned 429", retry_after=self._retry_after(response))
        if 500 <= status < 600:
            raise TransientLLMError(f"provider server error {status}", status_code=status)
        if not 200 <= status < 300:
            raise LLMHTTPStatusError(f"provider returned http {status}", status_code=status)
        return response.json()

    @staticmethod
    def _retry_after(response: Any) -> float | None:
        """Parse a ``Retry-After`` header (seconds) from ``response``, if any."""
        raw = response.headers.get("retry-after", None)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_transient_transport_error(exc: BaseException) -> bool:
        """Return whether ``exc`` is a retryable ``httpx`` transport error.

        Detection is by module + class name so this module never imports
        ``httpx`` (keeping ``import pirn_agents`` backend-free).
        """
        module = (type(exc).__module__ or "").split(".", 1)[0]
        if module != "httpx":
            return False
        transient_names = {
            "TimeoutException",
            "ConnectTimeout",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
            "ConnectError",
            "ReadError",
            "WriteError",
            "NetworkError",
            "TransportError",
            "RemoteProtocolError",
        }
        return type(exc).__name__ in transient_names
