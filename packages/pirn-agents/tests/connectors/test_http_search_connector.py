"""Mirrored tests for :class:`HttpSearchConnector` with an offline HTTP double (F16-S3).

The adapter is exercised through an :class:`HttpConnector` holding an injected
fake client, so no network is used. Tests cover generic JSON parsing, the
result cap, provider-neutral key configuration, consumption through the
:class:`SearchBackend` interface by :class:`WebSearchTool`, and lifecycle close.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.connectors.http_search_connector import HttpSearchConnector
from pirn_agents.tools.web.search_backend import SearchBackend
from pirn_agents.tools.web.web_search_tool import WebSearchTool


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        yield b""


class _FakeClient:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.calls: list[tuple[str, str, Any]] = []
        self.aclosed = False

    async def request(
        self, method: str, url: str, *, headers: Any = None, params: Any = None
    ) -> _FakeResponse:
        self.calls.append((method, url, params))
        return _FakeResponse(self._payload)

    async def aclose(self) -> None:
        self.aclosed = True


def _public_resolver(_host: str) -> str:
    return "93.184.216.34"


def _connector(payload: Any) -> tuple[HttpConnector, _FakeClient]:
    client = _FakeClient(payload)
    return HttpConnector(client=client, resolver=_public_resolver), client


class TestHttpSearchConnector:
    async def test_parses_generic_json_results(self) -> None:
        payload = {
            "results": [
                {"title": "A", "url": "https://a", "snippet": "sa"},
                {"title": "B", "url": "https://b", "snippet": "sb"},
            ]
        }
        http, client = _connector(payload)
        adapter = HttpSearchConnector(http=http, endpoint="https://search.example/api")
        results = await adapter.search("hello", max_results=5)
        assert results == [
            {"title": "A", "url": "https://a", "snippet": "sa"},
            {"title": "B", "url": "https://b", "snippet": "sb"},
        ]
        assert client.calls[0][2] == {"q": "hello"}

    async def test_result_cap(self) -> None:
        payload = {"results": [{"title": str(i), "url": f"https://{i}"} for i in range(10)]}
        http, _ = _connector(payload)
        adapter = HttpSearchConnector(http=http, endpoint="https://search.example/api")
        results = await adapter.search("q", max_results=3)
        assert len(results) == 3

    async def test_provider_neutral_key_and_param_config(self) -> None:
        payload = {"items": [{"name": "T", "link": "https://t", "text": "x"}]}
        http, client = _connector(payload)
        adapter = HttpSearchConnector(
            http=http,
            endpoint="https://other.example/find",
            query_param="query",
            results_key="items",
            title_key="name",
            url_key="link",
            snippet_key="text",
            extra_params={"lang": "en"},
        )
        results = await adapter.search("cats", max_results=5)
        assert results == [{"title": "T", "url": "https://t", "snippet": "x"}]
        assert client.calls[0][2] == {"query": "cats", "lang": "en"}

    async def test_is_a_search_backend_and_web_search_consumes_interface(self) -> None:
        payload = {"results": [{"title": "A", "url": "https://a", "snippet": "y" * 50}]}
        http, _ = _connector(payload)
        adapter = HttpSearchConnector(http=http, endpoint="https://search.example/api")
        assert isinstance(adapter, SearchBackend)
        # WebSearchTool consumes via the SearchBackend interface, not the concrete adapter.
        tool = WebSearchTool(backend=adapter, max_results=5, snippet_chars=10)
        result = await tool.invoke({"query": "hello"})
        assert result["count"] == 1
        assert result["results"][0]["snippet"] == "y" * 10

    async def test_close_closes_underlying_http(self) -> None:
        http, client = _connector({"results": []})
        adapter = HttpSearchConnector(http=http, endpoint="https://search.example/api")
        await adapter.close()
        assert client.aclosed is True

    def test_rejects_non_http_connector(self) -> None:
        with pytest.raises(TypeError, match="HttpConnector"):
            HttpSearchConnector(http=object(), endpoint="https://x")  # type: ignore[arg-type]

    def test_rejects_empty_endpoint(self) -> None:
        http, _ = _connector({})
        with pytest.raises(ValueError, match="endpoint"):
            HttpSearchConnector(http=http, endpoint="")
