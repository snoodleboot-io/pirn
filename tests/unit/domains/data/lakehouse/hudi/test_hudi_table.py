"""Unit tests for :class:`pirn.domains.data.lakehouse.hudi.hudi_table.HudiTable`.

The Hudi adapter is read-only by design; the write paths
(:meth:`append`, :meth:`overwrite`, :meth:`merge`) raise
:class:`NotImplementedError` pointing at the Hudi Spark/Java writer.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from datetime import UTC
from typing import Any

from pirn.domains.data.lakehouse.hudi.hudi_table import HudiTable
from pirn.domains.data.lakehouse.hudi.hudi_table_config import HudiTableConfig
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class StubTable:
    """Minimal stand-in for a Hudi vendor table."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, commits: list[Mapping[str, Any]] | None = None,) -> None:
        self._rows = list(rows or [])
        self._commits = list(commits or [])

    def scan_pylist(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows]

    def history(self) -> list[Mapping[str, Any]]:
        return list(self._commits)


async def _records(
    rows: list[dict[str, Any]],
) -> AsyncIterator[Mapping[str, Any]]:
    for row in rows:
        yield row


# ──────────────────────────────────────────────────────────── construction


class TestConstruction(unittest.TestCase):
    def test_rejects_no_args(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or table="):
            HudiTable()

    def test_rejects_wrong_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "HudiTableConfig"):
            HudiTable("not-a-config")  # type: ignore[arg-type]

    def test_rejects_empty_table_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "table_path"):
            HudiTable(HudiTableConfig(table_path=""))

    def test_rejects_invalid_table_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "table_type"):
            HudiTable(
                HudiTableConfig(
                    table_path="file:///t", table_type="STREAMING"
                )
            )

    def test_rejects_empty_record_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "record_key_field"):
            HudiTable(
                HudiTableConfig(
                    table_path="file:///t", record_key_field=""
                )
            )

    def test_rejects_empty_precombine(self) -> None:
        with self.assertRaisesRegex(ValueError, "precombine_field"):
            HudiTable(
                HudiTableConfig(
                    table_path="file:///t", precombine_field=""
                )
            )

    def test_accepts_injected_table(self) -> None:
        table = HudiTable(table=StubTable())
        assert isinstance(table, LakehouseTable)
        assert table.name == "<test-injected>"

    def test_name_uses_table_path(self) -> None:
        cfg = HudiTableConfig(table_path="file:///data/h")
        table = HudiTable(cfg, table=StubTable())
        assert table.name == "file:///data/h"


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        cfg = HudiTableConfig(table_path="file:///t")
        table = HudiTable(cfg, table=StubTable())
        await table.close()
        assert table._config is None
        assert table._table is None

    async def test_scan_after_close_raises(self) -> None:
        table = HudiTable(table=StubTable())
        await table.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await table.scan()


# ──────────────────────────────────────────────────────────── scan


class TestScan(unittest.IsolatedAsyncioTestCase):
    async def test_scan_yields_rows(self) -> None:
        rows = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        table = HudiTable(table=StubTable(rows=rows))
        out = [r async for r in await table.scan()]
        assert out == rows

    async def test_scan_columns_projects(self) -> None:
        rows = [{"id": 1, "v": "a", "extra": 9}]
        table = HudiTable(table=StubTable(rows=rows))
        out = [r async for r in await table.scan(columns=["id", "v"])]
        assert out == [{"id": 1, "v": "a"}]

    async def test_scan_filter_filters_in_python(self) -> None:
        rows = [
            {"id": 1, "region": "US"},
            {"id": 2, "region": "EU"},
        ]
        table = HudiTable(table=StubTable(rows=rows))
        out = [
            r async for r in await table.scan(filter={"region": "US"})
        ]
        assert out == [{"id": 1, "region": "US"}]

    async def test_scan_rejects_both_time_travel_args(self) -> None:
        from datetime import datetime

        table = HudiTable(table=StubTable())
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            await table.scan(
                snapshot_id=1,
                as_of_timestamp=datetime.now(UTC),
            )

    async def test_scan_requires_scan_pylist_on_stub(self) -> None:
        class NoScan:
            pass

        table = HudiTable(table=NoScan())
        with self.assertRaisesRegex(TypeError, "scan_pylist"):
            await table.scan()


# ──────────────────────────────────────────────────────────── writes raise


class TestWrites(unittest.IsolatedAsyncioTestCase):
    async def test_append_raises_not_implemented(self) -> None:
        table = HudiTable(table=StubTable())
        with self.assertRaisesRegex(NotImplementedError, "Spark/Java"):
            await table.append(_records([{"id": 1}]))

    async def test_overwrite_raises_not_implemented(self) -> None:
        table = HudiTable(table=StubTable())
        with self.assertRaisesRegex(NotImplementedError, "Spark/Java"):
            await table.overwrite(_records([{"id": 1}]))

    async def test_merge_raises_not_implemented(self) -> None:
        table = HudiTable(table=StubTable())
        with self.assertRaisesRegex(NotImplementedError, "Spark/Java"):
            await table.merge(_records([{"id": 1}]), on=["id"])


# ──────────────────────────────────────────────────────────── history


class TestHistory(unittest.IsolatedAsyncioTestCase):
    async def test_history_uses_stub_when_present(self) -> None:
        commits = [{"commit_time": "20260501000000", "operation": "upsert"}]
        table = HudiTable(table=StubTable(commits=commits))
        out = [c async for c in await table.history()]
        assert out == commits

    async def test_history_without_stub_raises_not_implemented(self) -> None:
        cfg = HudiTableConfig(table_path="file:///t")
        # No injected table; production path requires Hudi Java libs.
        # _scan_parquet path only runs for scan(); history() raises.
        # Use a minimal stub without history attr to exercise the
        # parquet-backed branch.
        class NoHistory:
            def scan_pylist(self) -> list[dict[str, Any]]:
                return []

        table = HudiTable(cfg, table=NoHistory())
        with self.assertRaisesRegex(NotImplementedError, "commit-timeline"):
            await table.history()
