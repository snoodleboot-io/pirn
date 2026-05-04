"""Unit tests for :class:`InfluxDBPool`.

Uses injected stubs — no real InfluxDB needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.timeseries.influxdb_config import InfluxDBConfig
from pirn.domains.connectors.timeseries.influxdb_pool import InfluxDBPool


# ──────────────────────────────────────────────────────────── fake objects


class FakeFluxRecord:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values


class FakeFluxTable:
    def __init__(self, records: list[FakeFluxRecord]) -> None:
        self.records = records


class FakeInfluxWriteAPI:
    def __init__(self) -> None:
        self.written: list[Any] = []

    async def write(self, bucket: str, org: str, record: Any) -> None:
        self.written.append({"bucket": bucket, "org": org, "record": record})


class FakeInfluxQueryAPI:
    def __init__(self, tables: list[FakeFluxTable] | None = None) -> None:
        self._tables = tables or []
        self.queries: list[str] = []

    async def query(self, query: str, org: str) -> list[FakeFluxTable]:
        self.queries.append(query)
        return self._tables


class FakeInfluxClient:
    def __init__(
        self,
        write_api: FakeInfluxWriteAPI | None = None,
        query_api: FakeInfluxQueryAPI | None = None,
    ) -> None:
        self._write_api = write_api or FakeInfluxWriteAPI()
        self._query_api = query_api or FakeInfluxQueryAPI()
        self.closed = False

    def write_api(self) -> FakeInfluxWriteAPI:
        return self._write_api

    def query_api(self) -> FakeInfluxQueryAPI:
        return self._query_api

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_config(**kwargs: Any) -> InfluxDBConfig:
    defaults = {"org": "myorg", "bucket": "mybucket"}
    defaults.update(kwargs)
    return InfluxDBConfig(**defaults)


def make_pool(client: FakeInfluxClient | None = None) -> InfluxDBPool:
    return InfluxDBPool(client=client or FakeInfluxClient())


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = make_pool()
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        InfluxDBPool()


# ───────────────────────────────────────────────────────────── config validation


def test_config_requires_org() -> None:
    with pytest.raises(ValueError, match="org"):
        InfluxDBConfig(org="", bucket="b")


def test_config_requires_bucket() -> None:
    with pytest.raises(ValueError, match="bucket"):
        InfluxDBConfig(org="o", bucket="")


def test_config_repr_redacts_token() -> None:
    cfg = make_config(token="super-secret-token")
    assert "super-secret-token" not in repr(cfg)
    assert "<redacted>" in repr(cfg)


# ───────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_writes_line_protocol(self) -> None:
        write_api = FakeInfluxWriteAPI()
        client = FakeInfluxClient(write_api=write_api)
        pool = InfluxDBPool(config=make_config(), client=client)
        # Inject APIs manually so _ensure_client doesn't try to call write_api()
        pool._write_api = write_api
        pool._query_api = client.query_api()
        result = await pool.execute("cpu,host=a value=1.0 1000000000")
        assert result == "OK"
        assert len(write_api.written) == 1
        assert write_api.written[0]["bucket"] == "mybucket"
        assert write_api.written[0]["org"] == "myorg"

    async def test_fetch_all_returns_rows(self) -> None:
        record = FakeFluxRecord({"_measurement": "cpu", "value": 1.0})
        table = FakeFluxTable([record])
        query_api = FakeInfluxQueryAPI(tables=[table])
        client = FakeInfluxClient(query_api=query_api)
        pool = InfluxDBPool(config=make_config(), client=client)
        pool._write_api = client.write_api()
        pool._query_api = query_api
        rows = await pool.fetch_all('from(bucket:"mybucket") |> range(start: -1h)')
        assert rows == [{"_measurement": "cpu", "value": 1.0}]

    async def test_acquire_returns_write_and_query_apis(self) -> None:
        fake_client = FakeInfluxClient()
        pool = InfluxDBPool(client=fake_client)
        handles = await pool.acquire()
        assert "write" in handles
        assert "query" in handles

    async def test_execute_many_writes_batch(self) -> None:
        write_api = FakeInfluxWriteAPI()
        client = FakeInfluxClient(write_api=write_api)
        pool = InfluxDBPool(config=make_config(), client=client)
        pool._write_api = write_api
        pool._query_api = client.query_api()
        await pool.execute_many(
            "ignored",
            [["cpu,host=a value=1.0"], ["cpu,host=b value=2.0"]],
        )
        assert len(write_api.written) == 1


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake_client = FakeInfluxClient()
        pool = InfluxDBPool(client=fake_client)
        await pool.close()
        assert fake_client.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = make_pool()
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = InfluxDBPool(config=make_config(), client=FakeInfluxClient())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = InfluxDBPool(config=make_config(), client=FakeInfluxClient())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


class TestCredentialSafety:
    def test_audit_dict_redacts_token(self) -> None:
        cfg = make_config(token="supersecrettoken")
        d = cfg.to_audit_dict()
        assert d["token"] == "<redacted>"
        assert "supersecrettoken" not in str(d)
