"""Unit tests for :class:`pirn.domains.data.lakehouse.iceberg.iceberg_table.IcebergTable`.

The vendor SDK (``pyiceberg``) is not required to run these tests — a
stub vendor table is injected via the ``table=`` constructor kwarg.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Mapping
import unittest
import unittest.mock

import pytest

from pirn.domains.data.lakehouse.iceberg.iceberg_table import IcebergTable
from pirn.domains.data.lakehouse.iceberg.iceberg_table_config import (
    IcebergTableConfig,
)
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class _ArrowResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def to_pylist(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _Scanner:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def to_arrow(self) -> _ArrowResult:
        return _ArrowResult(self._rows)


class _Snapshot:
    def __init__(self, snapshot_id: int) -> None:
        self.snapshot_id = snapshot_id


class _HistoryEntry:
    def __init__(self, snapshot_id: int, ts_ms: int, operation: str) -> None:
        self.snapshot_id = snapshot_id
        self.timestamp_ms = ts_ms
        self.parent_snapshot_id = None
        self.operation = operation


class StubTable:
    """Minimal stand-in for ``pyiceberg.table.Table``."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, snapshot_id: int = 1234,) -> None:
        self._rows = list(rows or [])
        self._snapshot_id = snapshot_id
        self.last_scan_kwargs: dict[str, Any] = {}
        self.appended: list[list[dict[str, Any]]] = []
        self.overwritten: list[dict[str, Any]] = []
        self._history = [
            _HistoryEntry(1, 1_000, "append"),
            _HistoryEntry(2, 2_000, "append"),
            _HistoryEntry(snapshot_id, 3_000, "overwrite"),
        ]

    def scan(self, **kwargs: Any) -> _Scanner:
        self.last_scan_kwargs = kwargs
        rows = self._rows
        if "selected_fields" in kwargs:
            cols = tuple(kwargs["selected_fields"])
            rows = [{c: r.get(c) for c in cols} for r in rows]
        return _Scanner(rows)

    def append(self, pa_table: Any) -> None:
        self.appended.append(pa_table.to_pylist())
        self._snapshot_id += 1

    def overwrite(self, pa_table: Any, **kwargs: Any) -> None:
        self.overwritten.append(
            {"rows": pa_table.to_pylist(), "kwargs": kwargs}
        )
        self._snapshot_id += 1

    def current_snapshot(self) -> _Snapshot:
        return _Snapshot(self._snapshot_id)

    def history(self) -> list[_HistoryEntry]:
        return list(self._history)


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


def _install_pyiceberg_expressions() -> None:
    """Patch sys.modules with a minimal pyiceberg.expressions stub."""
    expr_mod = types.ModuleType("pyiceberg.expressions")

    class _Expr:
        def __init__(self, kind: str, *args: Any) -> None:
            self.kind = kind
            self.args = args

        def __eq__(self, other: object) -> bool:
            return (
                isinstance(other, _Expr)
                and self.kind == other.kind
                and self.args == other.args
            )

        def __repr__(self) -> str:
            return f"{self.kind}{self.args}"

    def _eq(field: str, value: Any) -> _Expr:
        return _Expr("EqualTo", field, value)

    def _and(left: _Expr, right: _Expr) -> _Expr:
        return _Expr("And", left, right)

    expr_mod.EqualTo = _eq  # type: ignore[attr-defined]
    expr_mod.And = _and  # type: ignore[attr-defined]

    pyiceberg_mod = types.ModuleType("pyiceberg")
    pyiceberg_mod.expressions = expr_mod  # type: ignore[attr-defined]

    sys.modules["pyiceberg"] = pyiceberg_mod
    sys.modules["pyiceberg.expressions"] = expr_mod


async def _records(
    rows: list[dict[str, Any]],
) -> AsyncIterator[Mapping[str, Any]]:
    for row in rows:
        yield row


# ──────────────────────────────────────────────────────────── construction


class TestConstruction(unittest.TestCase):
    def test_rejects_no_args(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or table="):
            IcebergTable()

    def test_rejects_wrong_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "IcebergTableConfig"):
            IcebergTable("not-a-config")  # type: ignore[arg-type]

    def test_rejects_empty_table_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "table_identifier"):
            IcebergTable(IcebergTableConfig(catalog_name="default", table_identifier=""))

    def test_accepts_injected_table(self) -> None:
        table = IcebergTable(table=StubTable())
        assert isinstance(table, LakehouseTable)
        assert table.name == "<test-injected>"

    def test_name_uses_identifier(self) -> None:
        cfg = IcebergTableConfig(
            catalog_name="default", table_identifier="ns.tbl"
        )
        table = IcebergTable(cfg, table=StubTable())
        assert table.name == "ns.tbl"


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        cfg = IcebergTableConfig(
            catalog_name="default",
            catalog_properties={"uri": "https://x"},
            table_identifier="ns.tbl",
        )
        table = IcebergTable(cfg, table=StubTable())
        await table.close()
        assert table._config is None
        assert table._table is None

    async def test_scan_after_close_raises(self) -> None:
        table = IcebergTable(table=StubTable())
        await table.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await table.scan()


# ──────────────────────────────────────────────────────────── scan


class TestScan(unittest.IsolatedAsyncioTestCase):
    async def test_scan_yields_rows(self) -> None:
        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        stub = StubTable(rows=rows)
        table = IcebergTable(table=stub)
        out = [r async for r in await table.scan()]
        assert out == rows

    async def test_scan_columns_projects(self) -> None:
        rows = [{"id": 1, "name": "a", "extra": 99}]
        stub = StubTable(rows=rows)
        table = IcebergTable(table=stub)
        out = [r async for r in await table.scan(columns=["id", "name"])]
        assert out == [{"id": 1, "name": "a"}]
        assert stub.last_scan_kwargs["selected_fields"] == ("id", "name")

    async def test_scan_filter_builds_expression(self) -> None:
        _install_pyiceberg_expressions()
        self.addCleanup(lambda: [sys.modules.pop("pyiceberg", None), sys.modules.pop("pyiceberg.expressions", None)])
        stub = StubTable(rows=[{"id": 1}])
        table = IcebergTable(table=stub)
        async for _ in await table.scan(
            filter={"region": "US", "tier": "gold"}
        ):
            pass
        row_filter = stub.last_scan_kwargs["row_filter"]
        # The expression is an And(EqualTo, EqualTo).
        assert row_filter.kind == "And"

    async def test_scan_snapshot_id_passed(self) -> None:
        stub = StubTable(rows=[])
        table = IcebergTable(table=stub)
        async for _ in await table.scan(snapshot_id=42):
            pass
        assert stub.last_scan_kwargs["snapshot_id"] == 42

    async def test_scan_as_of_timestamp_resolves_snapshot(self) -> None:
        stub = StubTable(rows=[])
        table = IcebergTable(table=stub)
        ts = datetime.fromtimestamp(2.0, tz=timezone.utc)  # 2_000 ms
        async for _ in await table.scan(as_of_timestamp=ts):
            pass
        # Picks the snapshot at or before 2_000 ms — id=2.
        assert stub.last_scan_kwargs["snapshot_id"] == 2

    async def test_scan_as_of_timestamp_rejects_unreachable(self) -> None:
        stub = StubTable(rows=[])
        table = IcebergTable(table=stub)
        ts = datetime.fromtimestamp(0.0, tz=timezone.utc)
        with self.assertRaisesRegex(ValueError, "no snapshot"):
            async for _ in await table.scan(as_of_timestamp=ts):
                pass

    async def test_scan_rejects_both_time_travel_args(self) -> None:
        table = IcebergTable(table=StubTable())
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            await table.scan(
                snapshot_id=1,
                as_of_timestamp=datetime.now(timezone.utc),
            )


# ──────────────────────────────────────────────────────────── append/overwrite/merge


class TestWrites(unittest.IsolatedAsyncioTestCase):
    async def test_append_returns_snapshot_id_string(self) -> None:
        _stub_pyarrow_module()
        stub = StubTable(snapshot_id=10)
        table = IcebergTable(table=stub)
        snap = await table.append(_records([{"id": 1}, {"id": 2}]))
        assert snap == "11"
        assert stub.appended == [[{"id": 1}, {"id": 2}]]

    async def test_overwrite_passes_filter_expression(self) -> None:
        _stub_pyarrow_module()
        _install_pyiceberg_expressions()
        self.addCleanup(lambda: [sys.modules.pop("pyiceberg", None), sys.modules.pop("pyiceberg.expressions", None)])
        stub = StubTable(snapshot_id=20)
        table = IcebergTable(table=stub)
        snap = await table.overwrite(
            _records([{"id": 1, "region": "US"}]),
            partition_filter={"region": "US"},
        )
        assert snap == "21"
        assert "overwrite_filter" in stub.overwritten[0]["kwargs"]

    async def test_merge_raises_not_implemented(self) -> None:
        table = IcebergTable(table=StubTable())
        with self.assertRaisesRegex(NotImplementedError, "MERGE"):
            await table.merge(_records([{"id": 1}]), on=["id"])


# ──────────────────────────────────────────────────────────── history


class TestHistory(unittest.IsolatedAsyncioTestCase):
    async def test_history_yields_dict_entries(self) -> None:
        stub = StubTable(snapshot_id=99)
        table = IcebergTable(table=stub)
        commits = [c async for c in await table.history()]
        assert len(commits) == 3
        assert commits[0]["snapshot_id"] == 1
        assert commits[0]["timestamp_ms"] == 1_000
        assert commits[0]["operation"] == "append"
