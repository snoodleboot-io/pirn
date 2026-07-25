"""Mirrored tests for the web toolset with offline stub HTTP/search backends (PIR-151).

No network or real ``httpx`` is used: the HTTP tool takes an injected fake client
and an injected DNS resolver, and the search tool takes a stub backend. Covers
success, size-cap truncation, allowlist rejection, SSRF rejection, unsupported
method, and the friendly missing-``httpx`` install error (forced via
``patch.dict(sys.modules, {"httpx": None})``).
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any
from unittest import mock

import pytest

from pirn_agents.tools.web.html_to_text_tool import HtmlToTextTool
from pirn_agents.tools.web.http_request_tool import HttpRequestTool
from pirn_agents.tools.web.search_backend import SearchBackend
from pirn_agents.tools.web.web_search_tool import WebSearchTool


class _StubSearchBackend(SearchBackend):
    def __init__(self, results: Sequence[Mapping[str, Any]]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, max_results: int) -> Sequence[Mapping[str, Any]]:
        self.calls.append((query, max_results))
        return self._results


class _FakeResponse:
    def __init__(self, status: int, headers: dict[str, str], chunks: list[bytes]) -> None:
        self.status_code = status
        self.headers = headers
        self._chunks = chunks

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
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> _FakeStream:
        # url is the PINNED url (an IP literal); headers carries the original Host
        # and extensions the TLS sni_hostname (PIR-746).
        self.calls.append((method, url))
        self.headers = dict(headers) if headers else {}
        self.extensions = dict(extensions) if extensions else {}
        return _FakeStream(self._response)


def _public_resolver(_host: str) -> str:
    return "93.184.216.34"


def _loopback_resolver(_host: str) -> str:
    return "127.0.0.1"


class TestHtmlToText:
    async def test_strips_markup_and_scripts(self) -> None:
        tool = HtmlToTextTool()
        html = (
            "<html><body><h1>Title</h1><script>evil()</script><p>Hello &amp; bye</p></body></html>"
        )
        result = await tool.invoke({"html": html})
        assert "evil()" not in result["text"]
        assert "Title" in result["text"]
        assert "Hello & bye" in result["text"]
        assert result["truncated"] is False

    async def test_truncates_long_output(self) -> None:
        tool = HtmlToTextTool(max_chars=10)
        result = await tool.invoke({"html": "<p>" + "abc " * 100 + "</p>"})
        assert len(result["text"]) == 10
        assert result["truncated"] is True

    async def test_empty_html_allowed(self) -> None:
        tool = HtmlToTextTool()
        result = await tool.invoke({"html": ""})
        assert result["text"] == ""


class TestWebSearch:
    async def test_normalises_and_caps(self) -> None:
        backend = _StubSearchBackend(
            [
                {"title": "A", "url": "http://a", "snippet": "x" * 999},
                {"title": "B", "url": "http://b"},
                {"title": "C", "url": "http://c"},
            ]
        )
        tool = WebSearchTool(backend=backend, max_results=2, snippet_chars=10)
        result = await tool.invoke({"query": "hello"})
        assert result["count"] == 2
        assert result["results"][0] == {"title": "A", "url": "http://a", "snippet": "x" * 10}
        assert result["results"][1]["snippet"] == ""

    async def test_respects_requested_max_within_ceiling(self) -> None:
        backend = _StubSearchBackend([{"title": str(i), "url": f"http://{i}"} for i in range(10)])
        tool = WebSearchTool(backend=backend, max_results=5)
        result = await tool.invoke({"query": "q", "max_results": 3})
        assert result["count"] == 3
        assert backend.calls[-1] == ("q", 3)

    def test_rejects_non_backend(self) -> None:
        with pytest.raises(TypeError):
            WebSearchTool(backend=object())  # type: ignore[arg-type]


class TestHttpRequest:
    async def test_fetches_with_injected_client(self) -> None:
        response = _FakeResponse(200, {"Content-Type": "text/plain"}, [b"hello ", b"world"])
        client = _FakeClient(response)
        tool = HttpRequestTool(client=client, resolver=_public_resolver)
        result = await tool.invoke({"url": "https://example.com/page"})
        assert result["status"] == 200
        assert result["text"] == "hello world"
        assert result["truncated"] is False
        assert result["headers"]["content-type"] == "text/plain"
        # Pinned: the wire target is the vetted address, with the real hostname
        # restored via Host and TLS SNI so vhosts and cert verification still work.
        assert client.calls == [("GET", "https://93.184.216.34/page")]
        assert client.headers["Host"] == "example.com"
        assert client.extensions == {"sni_hostname": "example.com"}

    async def test_truncates_body_at_cap(self) -> None:
        response = _FakeResponse(200, {}, [b"a" * 50, b"b" * 50])
        tool = HttpRequestTool(
            client=_FakeClient(response), resolver=_public_resolver, max_bytes=30
        )
        result = await tool.invoke({"url": "https://example.com"})
        assert len(result["text"]) == 30
        assert result["truncated"] is True

    async def test_allowlist_rejection(self) -> None:
        tool = HttpRequestTool(
            client=_FakeClient(_FakeResponse(200, {}, [])),
            resolver=_public_resolver,
            allowed_hosts=("allowed.example",),
        )
        with pytest.raises(ValueError, match="not in allowed_hosts"):
            await tool.invoke({"url": "https://evil.example/x"})

    async def test_ssrf_rejection(self) -> None:
        tool = HttpRequestTool(
            client=_FakeClient(_FakeResponse(200, {}, [])),
            resolver=_loopback_resolver,
        )
        with pytest.raises(ValueError, match="private/loopback"):
            await tool.invoke({"url": "https://internal.example"})

    async def test_allow_private_skips_ssrf(self) -> None:
        response = _FakeResponse(200, {}, [b"ok"])
        tool = HttpRequestTool(
            client=_FakeClient(response),
            resolver=_loopback_resolver,
            allow_private=True,
        )
        result = await tool.invoke({"url": "http://localhost:8080/health"})
        assert result["text"] == "ok"

    async def test_unsupported_method(self) -> None:
        tool = HttpRequestTool(
            client=_FakeClient(_FakeResponse(200, {}, [])), resolver=_public_resolver
        )
        with pytest.raises(ValueError, match="unsupported method"):
            await tool.invoke({"url": "https://example.com", "method": "POST"})

    async def test_missing_httpx_raises_friendly_error(self) -> None:
        tool = HttpRequestTool(resolver=_public_resolver)
        with mock.patch.dict(sys.modules, {"httpx": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[web\]"'):
                await tool.invoke({"url": "https://example.com"})
