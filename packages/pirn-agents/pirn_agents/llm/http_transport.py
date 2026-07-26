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

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.llm.transient_llm_error import TransientLLMError


class HttpTransport:
    """Sends one POST with typed-error classification and backoff retries."""

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy,
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
        self._retry_policy: RetryPolicy = retry_policy
        self._sleep: Callable[[float], Awaitable[None]] = sleeper
        self._rng: Callable[[], float] | None = rng

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
        5xx/network errors up to the policy's ``max_retries``; propagates
        non-retryable errors immediately.
        """
        attempt = 0
        while True:
            try:
                return await self._post_json(
                    client=client, url=url, headers=headers, payload=payload
                )
            except RateLimitError as exc:
                if attempt >= self._retry_policy.max_retries:
                    raise
                if exc.retry_after is not None:
                    delay = min(exc.retry_after, self._retry_policy.max_retry_after)
                else:
                    delay = self._retry_policy.backoff_delay(attempt, rng=self._rng)
                await self._sleep(delay)
            except TransientLLMError:
                if attempt >= self._retry_policy.max_retries:
                    raise
                await self._sleep(self._retry_policy.backoff_delay(attempt, rng=self._rng))
            attempt += 1

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
