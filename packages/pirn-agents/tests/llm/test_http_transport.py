"""Unit tests for :class:`pirn_agents.llm.http_transport.HttpTransport`.

Exercises the extracted transport in isolation (retry loop, distinct 429
handling, transient/transport retries, non-retryable errors, ``Retry-After``
parsing, httpx-scoped transient detection) through the hermetic fake HTTP
transport — no network, no ``httpx`` import. Also asserts the security
invariant: no request header/credential ever leaks into a raised error.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn_agents.llm.http_transport import HttpTransport
from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.llm.transient_llm_error import TransientLLMError
from tests.llm.conftest import FakeAsyncClient, FakeResponse, RecordingSleeper

_URL = "https://stub.example/v1/complete"
_SECRET = "super-secret-key"
_HEADERS: dict[str, str] = {
    "content-type": "application/json",
    "authorization": f"Bearer {_SECRET}",
}


def _make_transport(sleeper: RecordingSleeper | None = None, **policy: Any) -> HttpTransport:
    return HttpTransport(
        retry_policy=RetryPolicy(**policy) if policy else RetryPolicy(),
        sleeper=sleeper if sleeper is not None else RecordingSleeper(),
        rng=lambda: 1.0,
    )


async def _request(transport: HttpTransport, client: FakeAsyncClient) -> Any:
    return await transport.request_with_retries(
        client=client, url=_URL, headers=_HEADERS, payload={"model": "m"}
    )


class TestPostAndClassify(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_json_on_2xx(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[FakeResponse(json_body={"ok": True})])
        transport = _make_transport()

        # Act
        data = await _request(transport, client)

        # Assert
        assert data == {"ok": True}
        assert client.post_calls[0]["url"] == _URL
        assert client.post_calls[0]["headers"]["authorization"] == f"Bearer {_SECRET}"

    async def test_5xx_raises_transient(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=503)])
        transport = _make_transport(max_retries=0)

        # Act / Assert
        with self.assertRaises(TransientLLMError):
            await _request(transport, client)

    async def test_non_2xx_4xx_raises_http_status(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=400)])
        transport = _make_transport(max_retries=0)

        # Act / Assert
        with self.assertRaises(LLMHTTPStatusError):
            await _request(transport, client)

    async def test_httpx_transport_error_wrapped_as_transient(self) -> None:
        # Arrange
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "httpx"
        client = FakeAsyncClient(post_results=[ReadTimeout("timed out")])
        transport = _make_transport(max_retries=0)

        # Act / Assert
        with self.assertRaises(TransientLLMError):
            await _request(transport, client)

    async def test_non_httpx_exception_propagates_unwrapped(self) -> None:
        # Arrange
        client = FakeAsyncClient(post_results=[ValueError("bad")])
        transport = _make_transport(max_retries=0)

        # Act / Assert
        with self.assertRaises(ValueError):
            await _request(transport, client)


class TestRetryLoop(unittest.IsolatedAsyncioTestCase):
    async def test_429_retried_and_honours_retry_after(self) -> None:
        # Arrange
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(
            post_results=[
                FakeResponse(status_code=429, headers={"retry-after": "1.5"}),
                FakeResponse(json_body={"ok": True}),
            ]
        )
        transport = _make_transport(sleeper)

        # Act
        data = await _request(transport, client)

        # Assert
        assert data == {"ok": True}
        assert sleeper.delays == [1.5]

    async def test_429_without_retry_after_uses_backoff(self) -> None:
        # Arrange
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(
            post_results=[FakeResponse(status_code=429), FakeResponse(json_body={})]
        )
        transport = HttpTransport(
            retry_policy=RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False),
            sleeper=sleeper,
            rng=lambda: 1.0,
        )

        # Act
        await _request(transport, client)

        # Assert
        assert sleeper.delays == [0.1]

    async def test_exhausts_retries_and_raises(self) -> None:
        # Arrange
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(post_results=[FakeResponse(status_code=429) for _ in range(3)])
        transport = HttpTransport(
            retry_policy=RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False),
            sleeper=sleeper,
            rng=lambda: 1.0,
        )

        # Act / Assert
        with self.assertRaises(RateLimitError):
            await _request(transport, client)
        assert sleeper.delays == [0.1, 0.2]

    async def test_transient_retried_then_succeeds(self) -> None:
        # Arrange
        sleeper = RecordingSleeper()
        client = FakeAsyncClient(
            post_results=[FakeResponse(status_code=503), FakeResponse(json_body={"ok": True})]
        )
        transport = _make_transport(sleeper)

        # Act
        data = await _request(transport, client)

        # Assert
        assert data == {"ok": True}
        assert len(sleeper.delays) == 1


class TestSecurityAndHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_error_messages_never_leak_credentials(self) -> None:
        # Arrange: each failure path must classify by status/exception only.
        cases = [
            FakeResponse(status_code=429),
            FakeResponse(status_code=503),
            FakeResponse(status_code=400),
        ]
        transport = _make_transport(max_retries=0)

        # Act / Assert: no raised message contains the secret or the auth header.
        for response in cases:
            client = FakeAsyncClient(post_results=[response])
            with self.assertRaises((RateLimitError, TransientLLMError, LLMHTTPStatusError)) as ctx:
                await _request(transport, client)
            assert _SECRET not in str(ctx.exception)
            assert "authorization" not in str(ctx.exception).lower()

    def test_retry_after_parses_and_tolerates_junk(self) -> None:
        # Arrange / Act / Assert
        assert HttpTransport._retry_after(FakeResponse(headers={"retry-after": "2.0"})) == 2.0
        assert HttpTransport._retry_after(FakeResponse(headers={"retry-after": "nope"})) is None
        assert HttpTransport._retry_after(FakeResponse()) is None

    def test_transient_detection_is_httpx_scoped(self) -> None:
        # Arrange
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "httpx"

        class ValueErrorLike(Exception):
            pass

        ValueErrorLike.__module__ = "builtins"

        # Act / Assert
        assert HttpTransport._is_transient_transport_error(ReadTimeout()) is True
        assert HttpTransport._is_transient_transport_error(ValueErrorLike()) is False


if __name__ == "__main__":
    unittest.main()
