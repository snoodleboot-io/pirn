"""Tests for LakehouseTableSink."""

from __future__ import annotations

import unittest
from typing import Any, AsyncIterator, Mapping, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable
from pirn.domains.data.lakehouse.lakehouse_table_sink import LakehouseTableSink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _FakeTable(LakehouseTable):
    def __init__(self, name: str = "fake_table") -> None:
        self._name = name
        self._appended: list[list[dict]] = []
        self._overwritten: list[dict] = []
        self._merged: list[dict] = []
        self._last_partition_filter: Any = None
        self._last_merge_on: Any = None

    @property
    def name(self) -> str:
        return self._name

    async def scan(self, **kwargs: Any) -> AsyncIterator[Mapping[str, Any]]:
        async def _gen() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield

        return _gen()

    async def append(self, records: AsyncIterator[Mapping[str, Any]]) -> str:
        rows: list[dict] = []
        async for row in records:
            rows.append(dict(row))
        self._appended.append(rows)
        return f"snap-append-{len(self._appended)}"

    async def overwrite(
        self, records: AsyncIterator[Mapping[str, Any]], *, partition_filter: Any = None
    ) -> str:
        rows: list[dict] = []
        async for row in records:
            rows.append(dict(row))
        self._overwritten.extend(rows)
        self._last_partition_filter = partition_filter
        return "snap-overwrite"

    async def merge(
        self, records: AsyncIterator[Mapping[str, Any]], *, on: Sequence[str]
    ) -> str:
        rows: list[dict] = []
        async for row in records:
            rows.append(dict(row))
        self._merged.extend(rows)
        self._last_merge_on = on
        return "snap-merge"

    async def history(self) -> AsyncIterator[Mapping[str, Any]]:
        async def _gen() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield

        return _gen()

    async def close(self) -> None:
        pass


class _BatchSource(Source):
    async def process(self, **_: Any) -> DataBatch:
        return DataBatch(rows=())


def _make_batch(rows: list[dict[str, Any]] | None = None) -> DataBatch:
    return DataBatch(rows=tuple(rows or []))


class TestLakehouseTableSinkConstruction(unittest.TestCase):
    def _table(self) -> _FakeTable:
        return _FakeTable()

    def test_rejects_non_lakehouse_table(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(TypeError, "LakehouseTable"):
                LakehouseTableSink(
                    batch=batch,
                    table=object(),  # type: ignore
                    _config=KnotConfig(id="sink"),
                )

    def test_rejects_invalid_mode(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(ValueError, "mode"):
                LakehouseTableSink(
                    batch=batch,
                    table=self._table(),
                    mode="upsert",  # invalid
                    _config=KnotConfig(id="sink"),
                )

    def test_merge_mode_requires_merge_on(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(ValueError, "merge_on"):
                LakehouseTableSink(
                    batch=batch,
                    table=self._table(),
                    mode="merge",
                    _config=KnotConfig(id="sink"),
                )

    def test_merge_mode_requires_non_empty_merge_on(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            with self.assertRaisesRegex(ValueError, "merge_on"):
                LakehouseTableSink(
                    batch=batch,
                    table=self._table(),
                    mode="merge",
                    merge_on=[],
                    _config=KnotConfig(id="sink"),
                )

    def test_append_mode_default(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=self._table(),
                _config=KnotConfig(id="sink"),
            )
        self.assertEqual(sink.mode, "append")

    def test_overwrite_mode(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=self._table(),
                mode="overwrite",
                _config=KnotConfig(id="sink"),
            )
        self.assertEqual(sink.mode, "overwrite")

    def test_merge_mode_with_keys(self) -> None:
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=self._table(),
                mode="merge",
                merge_on=["id"],
                _config=KnotConfig(id="sink"),
            )
        self.assertEqual(sink.mode, "merge")


class TestLakehouseTableSinkProcess(unittest.IsolatedAsyncioTestCase):
    def _table(self) -> _FakeTable:
        return _FakeTable()

    async def test_append_mode_calls_table_append(self) -> None:
        table = self._table()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                mode="append",
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([{"id": 1}, {"id": 2}]))
        self.assertTrue(result.startswith("snap-append"))
        self.assertEqual(len(table._appended[0]), 2)

    async def test_overwrite_mode_calls_table_overwrite(self) -> None:
        table = self._table()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                mode="overwrite",
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([{"id": 1}]))
        self.assertEqual(result, "snap-overwrite")
        self.assertEqual(len(table._overwritten), 1)

    async def test_overwrite_mode_passes_partition_filter(self) -> None:
        table = self._table()
        pf = {"region": "us-east"}
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                mode="overwrite",
                partition_filter=pf,
                _config=KnotConfig(id="sink"),
            )
        await sink.process(batch=_make_batch([{"id": 1}]))
        self.assertEqual(table._last_partition_filter, pf)

    async def test_merge_mode_calls_table_merge(self) -> None:
        table = self._table()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                mode="merge",
                merge_on=["id"],
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([{"id": 1}]))
        self.assertEqual(result, "snap-merge")
        self.assertEqual(list(table._last_merge_on), ["id"])

    async def test_process_returns_snapshot_id_string(self) -> None:
        table = self._table()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                _config=KnotConfig(id="sink"),
            )
        result = await sink.process(batch=_make_batch([]))
        self.assertIsInstance(result, str)

    async def test_append_empty_batch(self) -> None:
        table = self._table()
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            sink = LakehouseTableSink(
                batch=batch,
                table=table,
                _config=KnotConfig(id="sink"),
            )
        await sink.process(batch=_make_batch([]))
        self.assertEqual(table._appended[0], [])
