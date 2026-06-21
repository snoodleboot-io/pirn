"""Tests for LakehouseTableSink."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.lakehouse.lakehouse_table import LakehouseTable
from pirn_data.lakehouse.lakehouse_table_sink import LakehouseTableSink


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


def _make_sink(table: _FakeTable, **kwargs: Any) -> LakehouseTableSink:
    defaults: dict[str, Any] = {"table": table, "mode": "append"}
    defaults.update(kwargs)
    batch = _BatchSource(_config=KnotConfig(id="batch"))
    return LakehouseTableSink(batch=batch, _config=KnotConfig(id="sink"), **defaults)


class TestLakehouseTableSink(unittest.IsolatedAsyncioTestCase):
    def _table(self) -> _FakeTable:
        return _FakeTable()

    async def test_append_mode_calls_table_append(self) -> None:
        table = self._table()
        with Tapestry():
            sink = _make_sink(table, mode="append")
        result = await sink.process(
            batch=_make_batch([{"id": 1}, {"id": 2}]), table=table, mode="append"
        )
        assert result.startswith("snap-append")
        assert len(table._appended[0]) == 2

    async def test_overwrite_mode_calls_table_overwrite(self) -> None:
        table = self._table()
        with Tapestry():
            sink = _make_sink(table, mode="overwrite")
        result = await sink.process(batch=_make_batch([{"id": 1}]), table=table, mode="overwrite")
        assert result == "snap-overwrite"
        assert len(table._overwritten) == 1

    async def test_overwrite_mode_passes_partition_filter(self) -> None:
        table = self._table()
        pf = {"region": "us-east"}
        with Tapestry():
            sink = _make_sink(table, mode="overwrite", partition_filter=pf)
        await sink.process(
            batch=_make_batch([{"id": 1}]), table=table, mode="overwrite", partition_filter=pf
        )
        assert table._last_partition_filter == pf

    async def test_merge_mode_calls_table_merge(self) -> None:
        table = self._table()
        with Tapestry():
            sink = _make_sink(table, mode="merge", merge_on=["id"])
        result = await sink.process(
            batch=_make_batch([{"id": 1}]), table=table, mode="merge", merge_on=["id"]
        )
        assert result == "snap-merge"
        assert list(table._last_merge_on) == ["id"]

    async def test_process_returns_snapshot_id_string(self) -> None:
        table = self._table()
        with Tapestry():
            sink = _make_sink(table)
        result = await sink.process(batch=_make_batch([]), table=table, mode="append")
        assert isinstance(result, str)

    async def test_append_empty_batch(self) -> None:
        table = self._table()
        with Tapestry():
            sink = _make_sink(table)
        await sink.process(batch=_make_batch([]), table=table, mode="append")
        assert table._appended[0] == []


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_mode_from_upstream_knot(self) -> None:
        table = _FakeTable()

        @knot
        async def emit_mode() -> str:
            return "append"

        @knot
        async def emit_batch() -> DataBatch:
            return DataBatch(rows=({"id": 1},))

        with Tapestry() as t:
            batch_knot = emit_batch(_config=KnotConfig(id="batch"))
            mode_knot = emit_mode(_config=KnotConfig(id="mode"))
            LakehouseTableSink(
                batch=batch_knot,
                table=table,
                mode=mode_knot,
                _config=KnotConfig(id="sink"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sink"].startswith("snap-append")


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _table(self) -> _FakeTable:
        return _FakeTable()

    def _make_sink(self, **kwargs: Any) -> LakehouseTableSink:
        table = self._table()
        defaults: dict[str, Any] = {"table": table, "mode": "append"}
        defaults.update(kwargs)
        with Tapestry():
            batch = _BatchSource(_config=KnotConfig(id="batch"))
            return LakehouseTableSink(batch=batch, _config=KnotConfig(id="val"), **defaults)

    async def test_rejects_non_lakehouse_table(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(TypeError, "LakehouseTable"):
            await k.process(batch=_make_batch(), table=object(), mode="append")

    async def test_rejects_invalid_mode(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(ValueError, "mode"):
            await k.process(batch=_make_batch(), table=self._table(), mode="upsert")

    async def test_merge_mode_requires_merge_on(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(ValueError, "merge_on"):
            await k.process(
                batch=_make_batch(), table=self._table(), mode="merge", merge_on=None
            )

    async def test_merge_mode_requires_non_empty_merge_on(self) -> None:
        k = self._make_sink()
        with self.assertRaisesRegex(ValueError, "merge_on"):
            await k.process(
                batch=_make_batch(), table=self._table(), mode="merge", merge_on=[]
            )
