"""Unit tests for :class:`pirn.domains.data.lakehouse.delta.delta_table.DeltaTable`.

The vendor SDK (``deltalake``) is not required to run these tests — a
stub vendor table is injected via the ``dt=`` constructor kwarg, and
the ``write_deltalake`` / ``deltalake`` modules are stubbed in
``sys.modules`` for the write paths.
"""

from __future__ import annotations

import sys
import types
from typing import Any, AsyncIterator, Mapping
import unittest
import unittest.mock

from pirn.domains.data.lakehouse.delta.delta_table import DeltaTable
from pirn.domains.data.lakehouse.delta.delta_table_config import DeltaTableConfig
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class StubDt:
    """Minimal stand-in for ``deltalake.DeltaTable``."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, version_value: int = 7,) -> None:
        self._rows = list(rows or [])
        self._version = version_value
        self.loaded_version: int | None = None
        self.loaded_datetime: Any = None
        self.last_partitions: Any = None
        self.last_columns: Any = None
        self.merge_calls: list[dict[str, Any]] = []

    def to_pyarrow_table(self, partitions: Any = None, columns: Any = None,) -> Any:
        self.last_partitions = partitions
        self.last_columns = columns
        rows = self._rows
        if partitions is not None:
            for column, _, value in partitions:
                rows = [r for r in rows if r.get(column) == value]
        if columns is not None:
            rows = [{c: r.get(c) for c in columns} for r in rows]

        class _Table:
            def __init__(self, payload: list[dict[str, Any]]) -> None:
                self._payload = payload

            def to_pylist(self) -> list[dict[str, Any]]:
                return list(self._payload)

        return _Table(rows)

    def load_as_version(self, version: int) -> None:
        self.loaded_version = int(version)

    def load_with_datetime(self, ts: Any) -> None:
        self.loaded_datetime = ts

    def version(self) -> int:
        return self._version

    def update_incremental(self) -> None:
        self._version += 1

    def history(self) -> list[Mapping[str, Any]]:
        return [
            {"version": 0, "operation": "WRITE"},
            {"version": 1, "operation": "MERGE"},
        ]

    def merge(self, *, source: Any, predicate: str, source_alias: str, target_alias: str,) -> "_Builder":
        self.merge_calls.append(
            {
                "predicate": predicate,
                "source_alias": source_alias,
                "target_alias": target_alias,
                "rows": source.to_pylist(),
            }
        )
        outer = self

        class _Builder:
            def when_matched_update_all(self) -> "_Builder":
                return self

            def when_not_matched_insert_all(self) -> "_Builder":
                return self

            def execute(self) -> None:
                outer._version += 1

        return _Builder()


def _stub_pyarrow_module() -> Any:
    try:
        import pyarrow  # type: ignore[import-not-found]
    except ImportError:
        pa_mod = types.ModuleType("pyarrow")

        class _Table:
            def __init__(self, rows: list[dict[str, Any]]) -> None:
                self._rows = rows

            def to_pylist(self) -> list[dict[str, Any]]:
                return list(self._rows)

            @classmethod
            def from_pylist(cls, rows: list[dict[str, Any]]) -> "_Table":
                return cls(list(rows))

        pa_mod.Table = _Table  # type: ignore[attr-defined]
        sys.modules["pyarrow"] = pa_mod
        return pa_mod
    return pyarrow


async def _records(
    rows: list[dict[str, Any]],
) -> AsyncIterator[Mapping[str, Any]]:
    for row in rows:
        yield row


# ──────────────────────────────────────────────────────────── construction


class TestConstruction(unittest.TestCase):
    def test_rejects_no_args(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or dt="):
            DeltaTable()

    def test_rejects_wrong_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "DeltaTableConfig"):
            DeltaTable("not-a-config")  # type: ignore[arg-type]

    def test_rejects_empty_table_uri(self) -> None:
        with self.assertRaisesRegex(ValueError, "table_uri"):
            DeltaTable(DeltaTableConfig(table_uri=""))

    def test_accepts_injected_dt(self) -> None:
        table = DeltaTable(dt=StubDt())
        assert isinstance(table, LakehouseTable)
        assert table.name == "<test-injected>"

    def test_name_uses_table_uri(self) -> None:
        cfg = DeltaTableConfig(table_uri="s3://bucket/db/table")
        table = DeltaTable(cfg, dt=StubDt())
        assert table.name == "s3://bucket/db/table"


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        cfg = DeltaTableConfig(
            table_uri="s3://b/t", storage_options={"k": "v"}
        )
        table = DeltaTable(cfg, dt=StubDt())
        await table.close()
        assert table._config is None  # cleared via _clear_credentials
        assert table._dt is None

    async def test_scan_after_close_raises(self) -> None:
        table = DeltaTable(dt=StubDt())
        await table.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await table.scan()


# ──────────────────────────────────────────────────────────── scan


class TestScan(unittest.IsolatedAsyncioTestCase):
    async def test_scan_yields_rows(self) -> None:
        rows = [
            {"id": 1, "region": "US"},
            {"id": 2, "region": "EU"},
            {"id": 3, "region": "US"},
        ]
        dt = StubDt(rows=rows)
        table = DeltaTable(dt=dt)
        out: list[Mapping[str, Any]] = []
        async for row in await table.scan():
            out.append(row)
        assert out == rows

    async def test_scan_with_filter_pushes_partitions(self) -> None:
        rows = [
            {"id": 1, "region": "US"},
            {"id": 2, "region": "EU"},
        ]
        dt = StubDt(rows=rows)
        table = DeltaTable(dt=dt)
        out = [r async for r in await table.scan(filter={"region": "US"})]
        assert out == [{"id": 1, "region": "US"}]
        assert dt.last_partitions == [("region", "=", "US")]

    async def test_scan_with_columns_projects(self) -> None:
        rows = [{"id": 1, "name": "a", "extra": 9}]
        dt = StubDt(rows=rows)
        table = DeltaTable(dt=dt)
        out = [r async for r in await table.scan(columns=["id", "name"])]
        assert out == [{"id": 1, "name": "a"}]
        assert dt.last_columns == ["id", "name"]

    async def test_scan_snapshot_id_loads_version(self) -> None:
        dt = StubDt(rows=[])
        table = DeltaTable(dt=dt)
        async for _ in await table.scan(snapshot_id=5):
            pass
        assert dt.loaded_version == 5

    async def test_scan_as_of_timestamp_loads_datetime(self) -> None:
        from datetime import datetime, timezone

        dt = StubDt(rows=[])
        table = DeltaTable(dt=dt)
        ts = datetime(2026, 4, 30, tzinfo=timezone.utc)
        async for _ in await table.scan(as_of_timestamp=ts):
            pass
        assert dt.loaded_datetime == ts

    async def test_scan_rejects_both_time_travel_args(self) -> None:
        from datetime import datetime, timezone

        table = DeltaTable(dt=StubDt())
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            await table.scan(
                snapshot_id=1,
                as_of_timestamp=datetime.now(timezone.utc),
            )


# ──────────────────────────────────────────────────────────── append/overwrite/merge


class TestWrites(unittest.IsolatedAsyncioTestCase):
    def _install_write_stub(self) -> list[dict[str, Any]]:
        _stub_pyarrow_module()
        captured: list[dict[str, Any]] = []
        delta_mod = types.ModuleType("deltalake")

        def _write(target: Any, table: Any, **kwargs: Any) -> None:
            captured.append(
                {
                    "target": target,
                    "rows": table.to_pylist(),
                    "kwargs": kwargs,
                }
            )

        delta_mod.write_deltalake = _write  # type: ignore[attr-defined]
        delta_mod.DeltaTable = StubDt  # type: ignore[attr-defined]
        sys.modules["deltalake"] = delta_mod
        self.addCleanup(lambda: sys.modules.pop("deltalake", None))
        return captured

    async def test_append_returns_version_string(self) -> None:
        captured = self._install_write_stub()
        dt = StubDt(version_value=4)
        table = DeltaTable(dt=dt)
        version = await table.append(_records([{"id": 1}, {"id": 2}]))
        assert isinstance(version, str)
        assert version == "5"
        assert captured[0]["kwargs"]["mode"] == "append"
        assert captured[0]["rows"] == [{"id": 1}, {"id": 2}]

    async def test_overwrite_with_partition_filter_builds_predicate(self) -> None:
        captured = self._install_write_stub()
        dt = StubDt(version_value=10)
        table = DeltaTable(dt=dt)
        version = await table.overwrite(
            _records([{"id": 1, "region": "US"}]),
            partition_filter={"region": "US"},
        )
        assert version == "11"
        kwargs = captured[0]["kwargs"]
        assert kwargs["mode"] == "overwrite"
        assert kwargs["predicate"] == "region = 'US'"

    async def test_merge_builds_predicate_and_returns_version(self) -> None:
        self._install_write_stub()
        dt = StubDt(version_value=2)
        table = DeltaTable(dt=dt)
        version = await table.merge(
            _records([{"id": 1, "v": "x"}]),
            on=["id"],
        )
        assert version == "3"
        assert dt.merge_calls[0]["predicate"] == "target.id = source.id"
        assert dt.merge_calls[0]["rows"] == [{"id": 1, "v": "x"}]

    async def test_merge_rejects_empty_on(self) -> None:
        table = DeltaTable(dt=StubDt())
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await table.merge(_records([{"id": 1}]), on=[])


# ──────────────────────────────────────────────────────────── history


class TestHistory(unittest.IsolatedAsyncioTestCase):
    async def test_history_yields_commits(self) -> None:
        table = DeltaTable(dt=StubDt())
        commits = [c async for c in await table.history()]
        assert commits == [
            {"version": 0, "operation": "WRITE"},
            {"version": 1, "operation": "MERGE"},
        ]
