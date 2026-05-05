"""Tests for :class:`PolarsRename`."""

from __future__ import annotations
import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_rename import PolarsRename
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {"user_id": [1, 2], "user_name": ["alice", "bob"], "region": ["EU", "US"]}
        )
    )


class TestPolarsRename(unittest.IsolatedAsyncioTestCase):
    async def test_renames_columns(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsRename(
                batch=batch,
                mapping={"user_id": "id", "user_name": "name"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["renamed"]
        assert set(out.column_names) == {"id", "name", "region"}

    async def test_unknown_columns_are_silently_ignored(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsRename(
                batch=batch,
                mapping={"user_id": "id", "absent": "x"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["renamed"]
        assert "id" in out.column_names
        assert "x" not in out.column_names


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_mapping(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                PolarsRename(batch=batch, mapping={}, _config=KnotConfig(id="r"))
