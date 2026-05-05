"""Tests for :class:`DataBatchToTuplesKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.specializations.medallion.data_batch_to_tuples_knot import (
    DataBatchToTuplesKnot,
)
from pirn.tapestry import Tapestry


def _make_knot(column_names: list[str] | None = None) -> DataBatchToTuplesKnot:
    return DataBatchToTuplesKnot(
        batch=MagicMock(),
        column_names=column_names or ["id", "name"],
        _config=KnotConfig(id="to_tuples"),
    )


class TestDataBatchToTuplesKnot(unittest.IsolatedAsyncioTestCase):
    async def test_projects_rows_to_tuples(self) -> None:
        k = _make_knot()
        batch = DataBatch(rows=({"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}))
        result = await k.process(batch=batch, column_names=["id", "name"])
        assert result == [(1, "alice"), (2, "bob")]

    async def test_missing_columns_produce_none(self) -> None:
        k = _make_knot(["id", "missing"])
        batch = DataBatch(rows=({"id": 1},))
        result = await k.process(batch=batch, column_names=["id", "missing"])
        assert result == [(1, None)]

    async def test_empty_batch_returns_empty_list(self) -> None:
        k = _make_knot(["id"])
        batch = DataBatch(rows=())
        result = await k.process(batch=batch, column_names=["id"])
        assert result == []


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_batch_from_upstream_knot(self) -> None:
        batch = DataBatch(rows=({"id": 1, "name": "alice"},))

        @knot
        async def emit_batch() -> DataBatch:
            return batch

        with Tapestry() as t:
            b = emit_batch(_config=KnotConfig(id="batch"))
            k = DataBatchToTuplesKnot(
                batch=b,
                column_names=["id", "name"],
                _config=KnotConfig(id="to_tuples"),
            )
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id] == [(1, "alice")]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DataBatchToTuplesKnot:
        defaults: dict[str, Any] = {"column_names": ["id"]}
        defaults.update(kwargs)
        with Tapestry():
            return DataBatchToTuplesKnot(
                batch=MagicMock(), **defaults, _config=KnotConfig(id="val")
            )

    async def _call(self, k: DataBatchToTuplesKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "batch": DataBatch(rows=()),
            "column_names": ["id"],
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_empty_column_names(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_names"):
            await self._call(k, column_names=[])
