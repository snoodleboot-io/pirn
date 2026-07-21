"""Tests for the S5 egress policy + SSRF guard (PIR-267 / PIR-324, PIR-326, PIR-329).

Covers allowed hosts, denied hosts, allow-list misses, and private-range / SSRF
attempts, plus the **seam closure**: the same :class:`EgressPolicy` instance is a
drop-in ``Callable[[str], None]`` wired into the F16
:class:`HttpConnector` (``egress_policy=...``) and used to guard the F6
``http_request`` tool. The DNS resolver is injected so every check is offline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.security.egress_error import EgressError
from pirn_agents.security.egress_policy import EgressPolicy
from pirn_agents.tools.web.http_request_tool import HttpRequestTool


def _resolver(mapping: Mapping[str, str]) -> Any:
    """Return a DNS resolver stub backed by ``mapping`` (host -> IP)."""

    def _resolve(host: str) -> str:
        return mapping[host]

    return _resolve


# --- offline HTTP client double (mirrors the http_connector test stubs) --------


class _FakeResponse:
    def __init__(self, status: int, chunks: list[bytes] | None = None) -> None:
        self.status_code = status
        self.headers: dict[str, str] = {"content-type": "text/plain"}
        self._chunks = chunks or [b"ok"]

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
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Any = None,
        params: Any = None,
        extensions: Any = None,
    ):
        self.calls.append((method, url))
        return _FakeResponse(200)

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Any = None,
        params: Any = None,
        extensions: Any = None,
    ):
        self.calls.append((method, url))
        return _FakeStream(_FakeResponse(200))


# --- policy behaviour ----------------------------------------------------------


def test_allowed_public_host_passes() -> None:
    policy = EgressPolicy(resolver=_resolver({"api.example.com": "93.184.216.34"}))
    policy("https://api.example.com/data")  # does not raise
    assert policy.is_allowed("https://api.example.com/data")


def test_denied_host_blocked_first() -> None:
    policy = EgressPolicy(
        denied_hosts=("evil.example",),
        resolver=_resolver({"evil.example": "93.184.216.34"}),
    )
    with pytest.raises(EgressError) as excinfo:
        policy("https://evil.example/x")
    assert "deny-listed" in str(excinfo.value)
    assert excinfo.value.host == "evil.example"


def test_allow_list_miss_blocked() -> None:
    policy = EgressPolicy(
        allowed_hosts=("api.example.com",),
        resolver=_resolver({"other.example": "93.184.216.34"}),
    )
    assert not policy.is_allowed("https://other.example/x")


def test_private_range_blocked_by_default() -> None:
    policy = EgressPolicy(resolver=_resolver({"internal": "10.0.0.5"}))
    with pytest.raises(EgressError):
        policy("http://internal/admin")


def test_loopback_and_metadata_blocked() -> None:
    policy = EgressPolicy(resolver=_resolver({"lb": "127.0.0.1", "meta": "169.254.169.254"}))
    with pytest.raises(EgressError):
        policy("http://lb/")
    with pytest.raises(EgressError):
        policy("http://meta/latest/meta-data/")


def test_allow_private_opt_in() -> None:
    policy = EgressPolicy(allow_private=True, resolver=_resolver({"internal": "10.0.0.5"}))
    policy("http://internal/ok")  # does not raise


def test_non_http_scheme_blocked() -> None:
    policy = EgressPolicy(resolver=_resolver({}))
    with pytest.raises(EgressError):
        policy("file:///etc/passwd")


def test_bad_denied_hosts_type_rejected() -> None:
    with pytest.raises(TypeError):
        EgressPolicy(denied_hosts="evil.example")  # type: ignore[arg-type]


# --- SEAM CLOSURE: wire the policy into F16 HttpConnector -----------------------


async def test_egress_policy_wires_into_http_connector() -> None:
    # Arrange — one policy instance handed to the connector's egress seam.
    policy = EgressPolicy(
        denied_hosts=("blocked.example",),
        resolver=_resolver(
            {
                "api.example.com": "93.184.216.34",
                "blocked.example": "93.184.216.34",
                "internal": "10.0.0.9",
            }
        ),
    )
    client = _FakeClient()
    connector = HttpConnector(egress_policy=policy, client=client)

    # Act / Assert — allowed public host flows through to the pooled client.
    response = await connector.request("GET", "https://api.example.com/data")
    assert response.status_code == 200
    # Pinned to the vetted address (PIR-746); the hostname rides in the Host header.
    assert client.calls == [("GET", "https://93.184.216.34/data")]

    # A deny-listed host is refused by the policy before any request is made.
    with pytest.raises(EgressError):
        await connector.request("GET", "https://blocked.example/x")
    # A private-range host is refused by the SSRF guard inside the policy.
    with pytest.raises(EgressError):
        await connector.request("GET", "http://internal/admin")
    # No further client calls were recorded for the blocked requests.
    assert client.calls == [("GET", "https://93.184.216.34/data")]


# --- SEAM CLOSURE: guard the F6 http_request tool with the same policy ----------


async def test_egress_policy_guards_http_request_tool() -> None:
    # Arrange — the policy pre-screens URLs before the F6 tool runs.
    resolver = _resolver({"api.example.com": "93.184.216.34", "internal": "10.0.0.9"})
    policy = EgressPolicy(resolver=resolver)
    tool = HttpRequestTool(client=_FakeClient(), resolver=resolver)

    # Act / Assert — a private URL is blocked by the policy; the tool never runs.
    with pytest.raises(EgressError):
        policy("http://internal/secret")

    # An allowed public URL passes the policy and the tool returns its body.
    policy("https://api.example.com/data")
    result = await tool.invoke({"url": "https://api.example.com/data"})
    assert result["status"] == 200
    assert result["text"] == "ok"
