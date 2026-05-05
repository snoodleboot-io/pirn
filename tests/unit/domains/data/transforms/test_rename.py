"""Tests for :class:`pirn.domains.data.transforms.rename.Rename`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.transforms.rename import Rename
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DataBatch:
    schema = DataSchema(
        columns={"user_id": int, "user_name": str, "region": str},
        primary_keys=("user_id",),
        nullable=("region",),
    )
    rows = (
        {"user_id": 1, "user_name": "alice", "region": "EU"},
        {"user_id": 2, "user_name": "bob",   "region": None},
    )
    return DataBatch(rows=rows, schema=schema)


class TestRename(unittest.IsolatedAsyncioTestCase):
    async def test_renames_columns_and_passes_others_through(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Rename(
                batch=batch,
                mapping={"user_id": "id", "user_name": "name"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["renamed"]
        assert out.rows == (
            {"id": 1, "name": "alice", "region": "EU"},
            {"id": 2, "name": "bob",   "region": None},
        )

    async def test_updates_schema_columns_pks_and_nullable(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Rename(
                batch=batch,
                mapping={"user_id": "id", "user_name": "name"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["renamed"]
        assert out.schema.column_names == ("id", "name", "region")
        assert out.schema.primary_keys == ("id",)
        assert out.schema.nullable == ("region",)

    async def test_unmapped_columns_unchanged(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            Rename(
                batch=batch,
                mapping={"user_id": "id"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["renamed"]
        assert "user_name" in out.rows[0]
        assert "id" in out.rows[0]


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_mapping(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                Rename(batch=batch, mapping={}, _config=KnotConfig(id="r"))

    def test_rejects_non_string_keys(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "strings"):
                Rename(
                    batch=batch, mapping={1: "id"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="r"),
                )
