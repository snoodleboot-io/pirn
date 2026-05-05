"""Tests for LakehouseTableSource."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable
from pirn.domains.data.lakehouse.lakehouse_table_source import LakehouseTableSource


class _FakeTable(LakehouseTable):
    def __init__(self, rows: list[dict[str, Any]], name: str = "fake_table") -> None:
        self._rows = rows
        self._name = name
        self._last_scan_kwargs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self._name

    async def scan(
        self,
        *,
        snapshot_id: Any = None,
        as_of_timestamp: Any = None,
        filter: Any = None,
        columns: Any = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        self._last_scan_kwargs = {
            "snapshot_id": snapshot_id,
            "as_of_timestamp": as_of_timestamp,
            "filter": filter,
            "columns": columns,
        }

        async def _gen() -> AsyncIterator[Mapping[str, Any]]:
            for row in self._rows:
                yield row

        return _gen()

    async def append(self, records: Any) -> str:
        raise NotImplementedError

    async def overwrite(self, records: Any, *, partition_filter: Any = None) -> str:
        raise NotImplementedError

    async def merge(self, records: Any, *, on: Any) -> str:
        raise NotImplementedError

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class TestValidation(unittest.TestCase):
    def _make_table(self) -> _FakeTable:
        return _FakeTable([])

    def test_rejects_non_lakehouse_table(self) -> None:
        with self.assertRaisesRegex(TypeError, "LakehouseTable"):
            LakehouseTableSource(
                table=object(),  # type: ignore
                _config=KnotConfig(id="src"),
            )

    def test_rejects_both_snapshot_id_and_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            LakehouseTableSource(
                table=self._make_table(),
                snapshot_id=1,
                as_of_timestamp=datetime.now(UTC),
                _config=KnotConfig(id="src"),
            )

    def test_rejects_invalid_schema(self) -> None:
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            LakehouseTableSource(
                table=self._make_table(),
                schema=object(),  # type: ignore
                _config=KnotConfig(id="src"),
            )

    def test_snapshot_id_without_timestamp_is_valid(self) -> None:
        src = LakehouseTableSource(
            table=self._make_table(),
            snapshot_id=42,
            _config=KnotConfig(id="src"),
        )
        assert src is not None

    def test_timestamp_without_snapshot_id_is_valid(self) -> None:
        src = LakehouseTableSource(
            table=self._make_table(),
            as_of_timestamp=datetime.now(UTC),
            _config=KnotConfig(id="src"),
        )
        assert src is not None


class TestLakehouseTableSource(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_data_batch(self) -> None:
        table = _FakeTable([{"id": 1}, {"id": 2}])
        src = LakehouseTableSource(table=table, _config=KnotConfig(id="src"))
        batch = await src.process()
        assert isinstance(batch, DataBatch)

    async def test_process_rows_match_table_scan(self) -> None:
        rows = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
        table = _FakeTable(rows)
        src = LakehouseTableSource(table=table, _config=KnotConfig(id="src"))
        batch = await src.process()
        assert len(batch.rows) == 2
        assert batch.rows[0]["id"] == 1

    async def test_process_empty_table_returns_empty_batch(self) -> None:
        table = _FakeTable([])
        src = LakehouseTableSource(table=table, _config=KnotConfig(id="src"))
        batch = await src.process()
        assert batch.rows == ()

    async def test_process_passes_snapshot_id_to_scan(self) -> None:
        table = _FakeTable([])
        src = LakehouseTableSource(table=table, snapshot_id=99, _config=KnotConfig(id="src"))
        await src.process()
        assert table._last_scan_kwargs["snapshot_id"] == 99

    async def test_process_passes_filter_to_scan(self) -> None:
        table = _FakeTable([])
        filt = {"col": "val"}
        src = LakehouseTableSource(table=table, filter=filt, _config=KnotConfig(id="src"))
        await src.process()
        assert table._last_scan_kwargs["filter"] == filt

    async def test_process_passes_columns_to_scan(self) -> None:
        table = _FakeTable([])
        src = LakehouseTableSource(
            table=table, columns=["id", "name"], _config=KnotConfig(id="src")
        )
        await src.process()
        assert table._last_scan_kwargs["columns"] == ("id", "name")

    async def test_process_source_uri_contains_table_name(self) -> None:
        table = _FakeTable([], name="my_table")
        src = LakehouseTableSource(table=table, _config=KnotConfig(id="src"))
        batch = await src.process()
        assert "my_table" in batch.source_uri

    async def test_process_schema_propagated(self) -> None:
        schema = DataSchema(columns={"id": int})
        table = _FakeTable([{"id": 1}])
        src = LakehouseTableSource(table=table, schema=schema, _config=KnotConfig(id="src"))
        batch = await src.process()
        assert batch.schema == schema
