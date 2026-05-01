"""Unit tests for :class:`BigqueryPool`.

Uses an injected stub client that mirrors the slice of the
``google.cloud.bigquery.Client`` surface that the pool calls into. No
real BigQuery account needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.bigquery_config import BigqueryConfig
from pirn.domains.connectors.databases.bigquery_pool import BigqueryPool


# ──────────────────────────────────────────────────────────── fake client


class FakeQueryJob:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def result(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class FakeBigqueryClient:
    """Mirrors ``bigquery.Client.query`` and ``.close``."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, Any]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.closed = False

    def query(self, sql: str, job_config: Any | None = None) -> FakeQueryJob:
        self.queries.append((sql, job_config))
        return FakeQueryJob(self.responses.get(sql, []))

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = BigqueryPool(client=FakeBigqueryClient())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        BigqueryPool()


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        await pool.execute("INSERT INTO t (x) VALUES (@x)", [1])
        assert len(fake.queries) == 1
        sql, job_config = fake.queries[0]
        assert sql == "INSERT INTO t (x) VALUES (@x)"
        assert job_config is not None
        params = list(job_config.query_parameters)
        assert len(params) == 1
        # The pool may wrap bare values into a ScalarQueryParameter when the
        # real google-cloud-bigquery SDK is installed; accept either shape.
        wrapped = params[0]
        unwrapped = getattr(wrapped, "value", wrapped)
        assert unwrapped == 1

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeBigqueryClient()
        fake.responses["SELECT id FROM t"] = [(1,), (2,)]
        pool = BigqueryPool(client=fake)
        rows = await pool.fetch_all("SELECT id FROM t")
        assert rows == [(1,), (2,)]

    async def test_execute_many_runs_each_row(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (@a, @b)", [(1, "a"), (2, "b")]
        )
        assert len(fake.queries) == 2

    async def test_acquire_returns_client(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        assert await pool.acquire() is fake
        # release is a no-op
        await pool.release(fake)


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety:
    def test_rejects_fstring_placeholder(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation(
                "SELECT * FROM t WHERE x = {value}"
            )

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_named_parameter(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = @value")


@pytest.mark.asyncio
class TestQuerySafetyEnforced:
    async def test_execute_rejects_format_query(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        await pool.close()
        await pool.close()  # must not raise

    async def test_acquire_after_close_raises(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_credentials_path(self) -> None:
        cfg = BigqueryConfig(
            project_id="proj",
            credentials_path="/secrets/sa-key.json",
        )
        text = repr(cfg)
        assert "/secrets/sa-key.json" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_credentials_path(self) -> None:
        cfg = BigqueryConfig(
            project_id="proj",
            credentials_path="/secrets/sa-key.json",
        )
        d = cfg.to_audit_dict()
        assert d["credentials_path"] == "<redacted>"
        assert d["project_id"] == "proj"
