"""Mirrored tests for :class:`HttpConnector` with offline stub transports (F16-S1).

No network or real ``httpx`` is used: the connector takes an injected fake client
and an injected DNS resolver, so pooling reuse, retry/backoff, auth injection,
egress rejection, streaming, and the friendly missing-``httpx`` install error are
all exercised fully offline.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Mapping
from typing import Any
from unittest import mock

import pytest

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.credential_ref import CredentialRef


class _FakeResponse:
    def __init__(self, status: int, *, payload: Any = None, chunks: list[bytes] | None = None):
        self.status_code = status
        self.headers: dict[str, str] = {}
        self._payload = payload
        self._chunks = chunks or []

    def json(self) -> Any:
        return self._payload

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class _FakeStream:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, *_: object) -> bool:
        return False


class _FakeClient:
    """Records requests; can be scripted to raise or return retryable statuses."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, Mapping[str, str] | None]] = []
        self.aclosed = False

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Any = None,
        extensions: Any = None,
    ) -> _FakeResponse:
        self.calls.append((method, url, headers))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Any = None,
        params: Any = None,
        extensions: Any = None,
    ) -> _FakeStream:
        self.calls.append((method, url, headers))
        item = self._responses.pop(0)
        assert isinstance(item, _FakeResponse)
        return _FakeStream(item)

    async def aclose(self) -> None:
        self.aclosed = True


def _public_resolver(_host: str) -> str:
    return "93.184.216.34"


def _loopback_resolver(_host: str) -> str:
    return "127.0.0.1"


async def _noop_sleep(_seconds: float) -> None:
    return None


class TestHttpConnectorBasics:
    async def test_is_a_connector_base(self) -> None:
        connector = HttpConnector(client=_FakeClient([]), resolver=_public_resolver)
        assert isinstance(connector, ConnectorBase)

    async def test_request_reuses_single_pooled_client(self) -> None:
        client = _FakeClient([_FakeResponse(200), _FakeResponse(200), _FakeResponse(200)])
        connector = HttpConnector(client=client, resolver=_public_resolver)
        for _ in range(3):
            await connector.request("GET", "https://example.com/x")
        # Same injected client used every time -> the pooling lever.
        first = await connector._get_client()
        assert first is client
        assert len(client.calls) == 3

    async def test_bearer_auth_header_injected(self) -> None:
        client = _FakeClient([_FakeResponse(200)])
        connector = HttpConnector(
            client=client, resolver=_public_resolver, credential=CredentialRef("tok-123")
        )
        await connector.request("GET", "https://example.com")
        assert client.calls[0][2]["Authorization"] == "Bearer tok-123"

    async def test_api_key_auth_header_injected(self) -> None:
        client = _FakeClient([_FakeResponse(200)])
        connector = HttpConnector(
            client=client,
            resolver=_public_resolver,
            credential=CredentialRef("key-abc"),
            auth_scheme="api_key",
            api_key_header="X-Api-Key",
        )
        await connector.request("GET", "https://example.com")
        assert client.calls[0][2]["X-Api-Key"] == "key-abc"

    async def test_no_auth_when_scheme_none(self) -> None:
        client = _FakeClient([_FakeResponse(200)])
        connector = HttpConnector(
            client=client,
            resolver=_public_resolver,
            credential=CredentialRef("secret"),
            auth_scheme="none",
        )
        await connector.request("GET", "https://example.com")
        assert "Authorization" not in client.calls[0][2]

    async def test_base_url_join(self) -> None:
        client = _FakeClient([_FakeResponse(200)])
        connector = HttpConnector(
            client=client, resolver=_public_resolver, base_url="https://api.example.com/v1"
        )
        # Relative path must resolve to an absolute URL for the egress guard.
        await connector.request("GET", "/search")
        # The wire target is the *joined* URL, pinned to the vetted address. Before
        # PIR-746 the guard vetted the joined URL but the raw "/search" was sent —
        # checking one URL and requesting another.
        _method, url, headers = client.calls[0]
        assert url == "https://93.184.216.34/v1/search"
        assert headers is not None and headers["Host"] == "api.example.com"

    async def test_request_is_pinned_so_a_rebinding_resolver_cannot_win(self) -> None:
        """A resolver that flips to a private address must not be re-consulted.

        The guard resolves once and the request goes to that address, so there is
        no second lookup for a short-TTL attacker record to poison.
        """
        calls = 0

        def _rebinding(_host: str) -> str:
            nonlocal calls
            calls += 1
            return "93.184.216.34" if calls == 1 else "169.254.169.254"

        client = _FakeClient([_FakeResponse(200)])
        connector = HttpConnector(client=client, resolver=_rebinding)
        await connector.request("GET", "https://example.com/x")
        _method, url, headers = client.calls[0]
        assert url == "https://93.184.216.34/x"
        assert headers is not None and headers["Host"] == "example.com"
        # Exactly one lookup, so the flipped second answer is unreachable.
        assert calls == 1


class TestHttpConnectorRetries:
    async def test_retries_transient_exception_then_succeeds(self) -> None:
        client = _FakeClient([RuntimeError("boom"), RuntimeError("boom"), _FakeResponse(200)])
        connector = HttpConnector(
            client=client, resolver=_public_resolver, max_retries=3, sleep=_noop_sleep
        )
        response = await connector.request("GET", "https://example.com")
        assert response.status_code == 200
        assert len(client.calls) == 3

    async def test_retries_retryable_status_then_succeeds(self) -> None:
        client = _FakeClient([_FakeResponse(503), _FakeResponse(200)])
        connector = HttpConnector(
            client=client, resolver=_public_resolver, max_retries=2, sleep=_noop_sleep
        )
        response = await connector.request("GET", "https://example.com")
        assert response.status_code == 200

    async def test_exhausts_retries_and_raises(self) -> None:
        client = _FakeClient([RuntimeError("a"), RuntimeError("b")])
        connector = HttpConnector(
            client=client, resolver=_public_resolver, max_retries=1, sleep=_noop_sleep
        )
        with pytest.raises(RuntimeError):
            await connector.request("GET", "https://example.com")

    async def test_non_retryable_exception_propagates_immediately(self) -> None:
        client = _FakeClient([ValueError("nope"), _FakeResponse(200)])
        connector = HttpConnector(
            client=client,
            resolver=_public_resolver,
            max_retries=3,
            sleep=_noop_sleep,
            is_retryable_exception=lambda exc: not isinstance(exc, ValueError),
        )
        with pytest.raises(ValueError):
            await connector.request("GET", "https://example.com")
        assert len(client.calls) == 1

    async def test_backoff_delay_is_exponential_and_capped(self) -> None:
        connector = HttpConnector(
            client=_FakeClient([]),
            resolver=_public_resolver,
            backoff_base=0.1,
            backoff_cap=0.35,
        )
        assert connector._delay_for(0) == pytest.approx(0.1)
        assert connector._delay_for(1) == pytest.approx(0.2)
        assert connector._delay_for(2) == pytest.approx(0.35)  # capped


class TestHttpConnectorEgress:
    async def test_ssrf_rejects_loopback(self) -> None:
        connector = HttpConnector(client=_FakeClient([]), resolver=_loopback_resolver)
        with pytest.raises(ValueError, match="private/loopback"):
            await connector.request("GET", "https://internal.example")

    async def test_allowlist_rejection(self) -> None:
        connector = HttpConnector(
            client=_FakeClient([]),
            resolver=_public_resolver,
            allowed_hosts=("allowed.example",),
        )
        with pytest.raises(ValueError, match="not in allowed_hosts"):
            await connector.request("GET", "https://evil.example/x")

    async def test_custom_egress_policy_seam_overrides_default(self) -> None:
        # The F11 seam: a caller-supplied egress policy replaces the SSRF guard.
        seen: list[str] = []

        def deny_all(url: str) -> None:
            seen.append(url)
            raise ValueError("egress: blocked by policy")

        connector = HttpConnector(
            client=_FakeClient([_FakeResponse(200)]),
            resolver=_loopback_resolver,
            egress_policy=deny_all,
        )
        with pytest.raises(ValueError, match="blocked by policy"):
            await connector.request("GET", "https://anything.example")
        assert seen == ["https://anything.example"]


class TestHttpConnectorStreaming:
    async def test_stream_bytes_yields_chunks_without_buffering(self) -> None:
        client = _FakeClient([_FakeResponse(200, chunks=[b"ab", b"cd", b"ef"])])
        connector = HttpConnector(client=client, resolver=_public_resolver)
        chunks = [chunk async for chunk in connector.stream_bytes("GET", "https://example.com")]
        assert chunks == [b"ab", b"cd", b"ef"]

    async def test_stream_applies_egress_guard(self) -> None:
        connector = HttpConnector(client=_FakeClient([]), resolver=_loopback_resolver)
        with pytest.raises(ValueError, match="private/loopback"):
            async for _ in connector.stream_bytes("GET", "https://internal.example"):
                pass


class TestHttpConnectorLifecycleAndErrors:
    async def test_close_releases_pooled_client(self) -> None:
        client = _FakeClient([])
        connector = HttpConnector(client=client, resolver=_public_resolver)
        await connector.close()
        assert client.aclosed is True
        assert connector._client is None

    async def test_missing_httpx_raises_friendly_error(self) -> None:
        connector = HttpConnector(resolver=_public_resolver)
        with mock.patch.dict(sys.modules, {"httpx": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[web\]"'):
                await connector.request("GET", "https://example.com")

    def test_rejects_unknown_auth_scheme(self) -> None:
        with pytest.raises(ValueError, match="auth_scheme"):
            HttpConnector(auth_scheme="oauth")  # type: ignore[arg-type]

    def test_rejects_negative_max_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            HttpConnector(max_retries=-1)
