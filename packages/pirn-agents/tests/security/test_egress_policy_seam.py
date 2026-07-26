"""Seam-closure tests: the core ``EgressPolicy`` wired into agents' HTTP layer.

The pure ``EgressPolicy`` behaviour is covered in pirn-core's suite. These tests
prove the same policy instance is a drop-in for the F16
:class:`~pirn.connectors.http_connector.HttpConnector` egress seam and for
the F6 ``http_request`` tool. The DNS resolver is injected so every check is offline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
from pirn.connectors.http_connector import HttpConnector
from pirn.security.egress_error import EgressError
from pirn.security.egress_policy import EgressPolicy

from pirn_agents.tools.web.http_request_tool import HttpRequestTool


def _resolver(mapping: Mapping[str, str]) -> Any:
    """Return a DNS resolver stub backed by ``mapping`` (host -> IP)."""

    def _resolve(host: str) -> str:
        return mapping[host]

    return _resolve


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
