"""Tests for :class:`TuplesToDataBatchKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.specializations.medallion.tuples_to_data_batch_knot import (
    TuplesToDataBatchKnot,
)


def _make_knot(column_names: list[str] | None = None) -> TuplesToDataBatchKnot:
    return TuplesToDataBatchKnot(
        rows=MagicMock(),
        column_names=column_names or ["id", "name"],
        _config=KnotConfig(id="to_batch"),
    )


class TestTuplesToDataBatchKnot(unittest.IsolatedAsyncioTestCase):
    async def test_maps_tuples_to_dicts(self) -> None:
        k = _make_knot()
        result = await k.process(
            rows=[(1, "alice"), (2, "bob")], column_names=["id", "name"]
        )
        assert isinstance(result, DataBatch)
        assert result.rows == ({"id": 1, "name": "alice"}, {"id": 2, "name": "bob"})

    async def test_empty_rows_returns_empty_batch(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[], column_names=["id"])
        assert isinstance(result, DataBatch)
        assert result.rows == ()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [(1, "alice")]

        with Tapestry() as t:
            r = emit_rows(_config=KnotConfig(id="rows"))
            k = TuplesToDataBatchKnot(
                rows=r, column_names=["id", "name"], _config=KnotConfig(id="to_batch")
            )
        result = await t.run(RunRequest())
        batch = result.outputs[k.config.id]
        assert isinstance(batch, DataBatch)
        assert batch.rows == ({"id": 1, "name": "alice"},)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> TuplesToDataBatchKnot:
        defaults: dict[str, Any] = {"column_names": ["id"]}
        defaults.update(kwargs)
        with Tapestry():
            return TuplesToDataBatchKnot(
                rows=MagicMock(), **defaults, _config=KnotConfig(id="val")
            )

    async def _call(self, k: TuplesToDataBatchKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {"rows": [], "column_names": ["id"]}
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_empty_column_names(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_names"):
            await self._call(k, column_names=[])
