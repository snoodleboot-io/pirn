"""Tests for :class:`TuplesToDataBatchKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.specializations.medallion.tuples_to_data_batch_knot import (
    TuplesToDataBatchKnot,
)


class TestTuplesToDataBatchKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        knot = TuplesToDataBatchKnot(
            rows=MagicMock(),
            column_names=["id", "name"],
            _config=KnotConfig(id="to_batch"),
        )
        self.assertIsInstance(knot, TuplesToDataBatchKnot)

    def test_rejects_empty_column_names(self) -> None:
        with self.assertRaises(ValueError):
            TuplesToDataBatchKnot(
                rows=MagicMock(),
                column_names=[],
                _config=KnotConfig(id="to_batch"),
            )


class TestTuplesToDataBatchKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_maps_tuples_to_dicts(self) -> None:
        knot = TuplesToDataBatchKnot(
            rows=MagicMock(),
            column_names=["id", "name"],
            _config=KnotConfig(id="to_batch"),
        )
        result = await knot.process(rows=[(1, "alice"), (2, "bob")], **{})
        self.assertIsInstance(result, DataBatch)
        self.assertEqual(result.rows, ({"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}))

    async def test_empty_rows_returns_empty_batch(self) -> None:
        knot = TuplesToDataBatchKnot(
            rows=MagicMock(),
            column_names=["id"],
            _config=KnotConfig(id="to_batch"),
        )
        result = await knot.process(rows=[], **{})
        self.assertIsInstance(result, DataBatch)
        self.assertEqual(result.rows, ())
