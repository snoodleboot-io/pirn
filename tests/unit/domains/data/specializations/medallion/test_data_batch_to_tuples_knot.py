"""Tests for :class:`DataBatchToTuplesKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.specializations.medallion.data_batch_to_tuples_knot import (
    DataBatchToTuplesKnot,
)
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _BatchSource(Source):
    async def process(self, **_: Any) -> DataBatch:
        return DataBatch(rows=())


class TestDataBatchToTuplesKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _BatchSource(_config=KnotConfig(id="src"))
            knot = DataBatchToTuplesKnot(
                batch=src,
                column_names=["id", "name"],
                _config=KnotConfig(id="to_tuples"),
            )
        self.assertIsInstance(knot, DataBatchToTuplesKnot)

    def test_rejects_empty_column_names(self) -> None:
        with Tapestry():
            src = _BatchSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                DataBatchToTuplesKnot(batch=src, column_names=[], _config=KnotConfig(id="to_tuples"))


class TestDataBatchToTuplesKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_projects_rows_to_tuples(self) -> None:
        with Tapestry():
            src = _BatchSource(_config=KnotConfig(id="src"))
            knot = DataBatchToTuplesKnot(batch=src, column_names=["id", "name"], _config=KnotConfig(id="to_tuples"))
        batch = DataBatch(rows=({"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}))
        result = await knot.process(batch=batch)
        self.assertEqual(result, [(1, "alice"), (2, "bob")])

    async def test_missing_columns_produce_none(self) -> None:
        with Tapestry():
            src = _BatchSource(_config=KnotConfig(id="src"))
            knot = DataBatchToTuplesKnot(batch=src, column_names=["id", "missing"], _config=KnotConfig(id="to_tuples"))
        batch = DataBatch(rows=({"id": 1},))
        result = await knot.process(batch=batch)
        self.assertEqual(result, [(1, None)])

    async def test_empty_batch_returns_empty_list(self) -> None:
        with Tapestry():
            src = _BatchSource(_config=KnotConfig(id="src"))
            knot = DataBatchToTuplesKnot(batch=src, column_names=["id"], _config=KnotConfig(id="to_tuples"))
        batch = DataBatch(rows=())
        result = await knot.process(batch=batch)
        self.assertEqual(result, [])
