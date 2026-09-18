"""Unit tests for :class:`BigqueryPool`.

Uses an injected stub client that mirrors the slice of the
``google.cloud.bigquery.Client`` surface that the pool calls into. No
real BigQuery account needed.

Every statement builds a real ``bigquery.QueryJobConfig``; the SDK is an optional
extra, so these tests stand a fake module in ``sys.modules`` for the duration
(PIR-873). The pool used to fall back to a ``BigqueryStubJobConfig`` of its own
when the import failed — production code that only existed to keep these tests
offline, and which would have handed a real client an object it cannot read.
"""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.bigquery_config import BigqueryConfig
from pirn.connectors.databases.bigquery_pool import BigqueryPool

# ──────────────────────────────────────────────────────────── fake client


class FakeScalarQueryParameter:
    """``bigquery.ScalarQueryParameter`` as the pool constructs it."""

    def __init__(self, name: str | None, type_: str, value: Any) -> None:
        self.name = name
        self.type_ = type_
        self.value = value

    def to_api_repr(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type_, "value": self.value}


class FakeQueryJobConfig:
    """``bigquery.QueryJobConfig`` as the pool constructs it."""

    def __init__(self, query_parameters: list[Any] | None = None) -> None:
        self.query_parameters = list(query_parameters or [])


def _fake_bigquery() -> mock._patch_dict:
    """Patch ``sys.modules`` so the lazy ``google.cloud.bigquery`` import finds the fake."""
    return mock.patch.dict(
        sys.modules,
        {
            "google.cloud.bigquery": SimpleNamespace(
                QueryJobConfig=FakeQueryJobConfig,
                ScalarQueryParameter=FakeScalarQueryParameter,
            )
        },
    )


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


class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        assert isinstance(pool, DatabaseConnectionPool)

    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            BigqueryPool()


# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        with _fake_bigquery():
            await pool.execute("INSERT INTO t (x) VALUES (@x)", [1])
        assert len(fake.queries) == 1
        sql, job_config = fake.queries[0]
        assert sql == "INSERT INTO t (x) VALUES (@x)"
        assert job_config is not None
        params = list(job_config.query_parameters)
        assert len(params) == 1
        # A bare value is wrapped into a typed ScalarQueryParameter — BigQuery
        # takes no untyped binds.
        assert params[0].value == 1
        assert params[0].type_ == "INT64"

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeBigqueryClient()
        fake.responses["SELECT id FROM t"] = [(1,), (2,)]
        pool = BigqueryPool(client=fake)
        with _fake_bigquery():
            rows = await pool.fetch_all("SELECT id FROM t")
        assert rows == [(1,), (2,)]

    async def test_execute_many_runs_each_row(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        with _fake_bigquery():
            await pool.execute_many("INSERT INTO t VALUES (@a, @b)", [(1, "a"), (2, "b")])
        assert len(fake.queries) == 2

    async def test_acquire_returns_client(self) -> None:
        fake = FakeBigqueryClient()
        pool = BigqueryPool(client=fake)
        assert await pool.acquire() is fake
        # release is a no-op
        await pool.release(fake)


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool.reject_inline_interpolation("SELECT * FROM t WHERE x = {value}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool.reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_named_parameter(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        pool.reject_inline_interpolation("SELECT * FROM t WHERE x = @value")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
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


class TestMissingBackend(unittest.IsolatedAsyncioTestCase):
    """A missing ``google-cloud-bigquery`` is reported, never worked around (PIR-873)."""

    async def test_execute_without_the_sdk_raises_the_install_hint(self) -> None:
        pool = BigqueryPool(client=FakeBigqueryClient())
        with mock.patch.dict(sys.modules, {"google.cloud.bigquery": None}):
            with self.assertRaisesRegex(ImportError, r'pip install "pirn-core\[bigquery\]"'):
                await pool.execute("SELECT 1")
