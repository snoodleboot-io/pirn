"""Concurrent-fetch throughput micro-benchmark for the web toolset (PIR-183).

Marked ``@pytest.mark.benchmark``. Like the F1 executor benchmark it measures
wall-clock directly with :func:`time.perf_counter` and does not depend on the
pytest-benchmark plugin. A fake async HTTP client with a fixed per-call delay
stands in for the network, so the test proves that async I/O lets N concurrent
``http_request`` invocations approach the slowest single call rather than their
serial sum.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import pytest

from pirn_agents.tools.web.http_request_tool import HttpRequestTool


class _SlowResponse:
    def __init__(self, delay: float) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self._delay = delay

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        await asyncio.sleep(self._delay)
        yield b"ok"


class _SlowStream:
    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def __aenter__(self) -> _SlowResponse:
        return _SlowResponse(self._delay)

    async def __aexit__(self, *_: object) -> bool:
        return False


class _SlowClient:
    def __init__(self, delay: float) -> None:
        self._delay = delay

    def stream(self, method: str, url: str) -> _SlowStream:
        return _SlowStream(self._delay)


def _public_resolver(_host: str) -> str:
    return "93.184.216.34"


@pytest.mark.benchmark
async def test_concurrent_fetch_beats_serial() -> None:
    n = 12
    per_call = 0.05
    tool = HttpRequestTool(client=_SlowClient(per_call), resolver=_public_resolver)

    start = time.perf_counter()
    results = await asyncio.gather(
        *(tool.invoke({"url": f"https://example.com/{i}"}) for i in range(n))
    )
    elapsed = time.perf_counter() - start

    assert len(results) == n
    assert all(r["text"] == "ok" for r in results)
    serial_lower_bound = n * per_call
    # Concurrency must beat serial execution by a wide margin (loose bound to
    # stay non-flaky on a busy CI host).
    assert elapsed < serial_lower_bound * 0.5
    print(f"[benchmark] web_concurrent_fetch n={n} per_call={per_call:.4g} elapsed={elapsed:.4g}")
