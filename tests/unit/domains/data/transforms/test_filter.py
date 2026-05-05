"""Tests for :class:`pirn.domains.data.transforms.filter.Filter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.transforms.filter import Filter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DataBatch:
    schema = DataSchema(columns={"id": int, "active": bool, "region": str})
    rows = (
        {"id": 1, "active": True,  "region": "EU"},
        {"id": 2, "active": False, "region": "US"},
        {"id": 3, "active": True,  "region": "US"},
        {"id": 4, "active": False, "region": "EU"},
    )
    return DataBatch(rows=rows, schema=schema)


class TestFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_only_rows_matching_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Filter(
                batch=batch,
                predicate=lambda r: r["active"],
                _config=KnotConfig(id="active_only"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["active_only"]
        assert tuple(r["id"] for r in out.rows) == (1, 3)

    async def test_preserves_schema(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Filter(
                batch=batch,
                predicate=lambda r: r["region"] == "EU",
                _config=KnotConfig(id="eu"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["eu"]
        assert out.schema.column_names == ("id", "active", "region")

    async def test_drops_all_when_predicate_never_true(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Filter(
                batch=batch,
                predicate=lambda _: False,
                _config=KnotConfig(id="empty"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["empty"]
        assert out.row_count == 0


class TestConstruction(unittest.TestCase):
    def test_rejects_non_callable_predicate(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "callable"):
                Filter(
                    batch=batch, predicate="not callable",  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )
