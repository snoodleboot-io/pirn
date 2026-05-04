"""Unit tests for :class:`VictoriaMetricsPool`.

Uses an injected httpx-style stub — no real VictoriaMetrics needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.timeseries.victoriametrics_config import (
    VictoriaMetricsConfig,
)
from pirn.domains.connectors.timeseries.victoriametrics_pool import VictoriaMetricsPool


# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHTTPXClient:
    def __init__(self, query_result: list[Any] | None = None) -> None:
        self.posted: list[dict[str, Any]] = []
        self.queries: list[str] = []
        self._query_result = query_result or []
        self.closed = False

    async def post(
        self, url: str, content: str, headers: dict[str, str] | None = None
    ) -> FakeHTTPXResponse:
        self.posted.append({"url": url, "content": content})
        return FakeHTTPXResponse({}, status_code=204)

    async def get(
        self, url: str, params: dict[str, str] | None = None
    ) -> FakeHTTPXResponse:
        self.queries.append((params or {}).get("query", ""))
        return FakeHTTPXResponse(
            {"data": {"result": self._query_result}}
        )

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = VictoriaMetricsPool(client=FakeHTTPXClient())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        VictoriaMetricsPool()


# ───────────────────────────────────────────────────────────── config


def test_config_repr_redacts_password() -> None:
    cfg = VictoriaMetricsConfig(username="alice", password="s3cr3t")
    assert "s3cr3t" not in repr(cfg)
    assert "<redacted>" in repr(cfg)


# ───────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_posts_prometheus_line(self) -> None:
        fake = FakeHTTPXClient()
        pool = VictoriaMetricsPool(client=fake)
        result = await pool.execute('cpu_usage{host="a"} 0.9 1234567890')
        assert result == "OK"
        assert len(fake.posted) == 1
        assert fake.posted[0]["url"] == "/api/v1/import/prometheus"
        assert 'cpu_usage{host="a"}' in fake.posted[0]["content"]

    async def test_fetch_all_returns_result_list(self) -> None:
        result_data = [
            {"metric": {"__name__": "cpu_usage"}, "value": [1234567890, "0.9"]}
        ]
        fake = FakeHTTPXClient(query_result=result_data)
        pool = VictoriaMetricsPool(client=fake)
        rows = await pool.fetch_all("cpu_usage")
        assert rows == result_data

    async def test_execute_many_posts_batch(self) -> None:
        fake = FakeHTTPXClient()
        pool = VictoriaMetricsPool(client=fake)
        await pool.execute_many(
            "ignored",
            [['cpu{host="a"} 0.9'], ['cpu{host="b"} 0.8']],
        )
        assert len(fake.posted) == 1

    async def test_acquire_returns_client(self) -> None:
        fake = FakeHTTPXClient()
        pool = VictoriaMetricsPool(client=fake)
        acquired = await pool.acquire()
        assert acquired is fake


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeHTTPXClient()
        pool = VictoriaMetricsPool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = VictoriaMetricsPool(client=FakeHTTPXClient())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()
