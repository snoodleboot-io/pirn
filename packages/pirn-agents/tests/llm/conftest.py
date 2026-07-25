"""Shared fake HTTP transport doubles for LLM provider connector tests.

These doubles mimic just enough of ``httpx.AsyncClient`` for the provider
connectors to run with **no** network and **no** ``httpx`` import, so the
suite stays hermetic and backend-free. They are injected via the provider's
``client=`` parameter.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any


class FakeResponse:
    """A non-streaming response double exposing ``status_code``/``json``/``headers``."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_body: Any = json_body if json_body is not None else {}
        self.headers: dict[str, str] = headers or {}

    def json(self) -> Any:
        return self._json_body


class FakeStream:
    """An async-context-manager stream double mimicking ``client.stream(...)``.

    Records whether it was entered and closed so tests can assert the
    underlying connection is released even on early exit / error.
    """

    def __init__(
        self,
        *,
        status_code: int = 200,
        lines: Sequence[str] = (),
        raise_after: int | None = None,
    ) -> None:
        self.status_code = status_code
        self._lines = list(lines)
        self._raise_after = raise_after
        self.entered = False
        self.closed = False

    async def __aenter__(self) -> FakeStream:
        self.entered = True
        return self

    async def __aexit__(self, *_exc: Any) -> bool:
        self.closed = True
        return False

    async def aiter_lines(self) -> AsyncIterator[str]:
        for position, line in enumerate(self._lines):
            if self._raise_after is not None and position >= self._raise_after:
                raise RuntimeError("stream boom")
            yield line


class FakeAsyncClient:
    """A fake ``httpx.AsyncClient`` scripting POST results and one stream.

    ``post_results`` is consumed in order; an entry may be a
    :class:`FakeResponse` (returned) or an :class:`Exception` (raised) to
    simulate transport failures / rate limits. ``stream`` is a
    :class:`FakeStream` or a zero-arg factory returning one.
    """

    def __init__(
        self,
        *,
        post_results: Sequence[Any] = (),
        stream: Any = None,
        repeat_last: bool = False,
    ) -> None:
        self._post_results = list(post_results)
        self._stream = stream
        self._repeat_last = repeat_last
        self._last_result: Any = None
        self.post_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []
        self.aclosed = False

    async def post(self, url: str, *, json: Any, headers: dict[str, str]) -> FakeResponse:
        self.post_calls.append({"url": url, "json": json, "headers": headers})
        if not self._post_results:
            if self._repeat_last and self._last_result is not None:
                result = self._last_result
            else:
                raise AssertionError("FakeAsyncClient: no scripted post result remaining")
        else:
            result = self._post_results.pop(0)
            self._last_result = result
        if isinstance(result, Exception):
            raise result
        return result

    def stream(self, method: str, url: str, *, json: Any, headers: dict[str, str]) -> FakeStream:
        self.stream_calls.append({"method": method, "url": url, "json": json, "headers": headers})
        if callable(self._stream):
            return self._stream()
        if self._stream is None:
            raise AssertionError("FakeAsyncClient: no scripted stream")
        return self._stream

    async def aclose(self) -> None:
        self.aclosed = True


class RecordingSleeper:
    """An async sleep double that records requested delays without waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
