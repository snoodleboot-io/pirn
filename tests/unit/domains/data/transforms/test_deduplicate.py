"""Tests for :class:`pirn.domains.data.transforms.deduplicate.Deduplicate`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.transforms.deduplicate import Deduplicate
from pirn.tapestry import Tapestry


@knot
async def emit_with_dups() -> DataBatch:
    rows = (
        {"id": 1, "version": 1, "name": "alice"},
        {"id": 2, "version": 1, "name": "bob"},
        {"id": 1, "version": 2, "name": "alice-v2"},  # dup on id
        {"id": 3, "version": 1, "name": "carol"},
        {"id": 2, "version": 2, "name": "bob-v2"},    # dup on id
    )
    return DataBatch(rows=rows)


class TestDeduplicate(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_first_occurrence_of_each_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            Deduplicate(
                batch=batch,
                keys=("id",),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dedup"]
        assert tuple(r["id"] for r in out.rows) == (1, 2, 3)
        # Confirm first occurrence (not the duplicate) was kept.
        assert out.rows[0]["name"] == "alice"
        assert out.rows[1]["name"] == "bob"

    async def test_composite_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            Deduplicate(
                batch=batch,
                keys=("id", "version"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dedup"]
        # Composite key (id, version) is unique across all rows → no drops.
        assert out.row_count == 5

    async def test_unhashable_value_does_not_crash(self) -> None:
        @knot
        async def with_list_value() -> DataBatch:
            rows = (
                {"id": 1, "tags": ["a", "b"]},
                {"id": 1, "tags": ["a", "b"]},  # equivalent — should dedup
            )
            return DataBatch(rows=rows)

        with Tapestry() as t:
            batch = with_list_value(_config=KnotConfig(id="batch"))
            Deduplicate(
                batch=batch,
                keys=("id", "tags"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dedup"]
        assert out.row_count == 1


class TestConstruction(unittest.TestCase):
    def test_rejects_string_keys_argument(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "sequence"):
                Deduplicate(
                    batch=batch, keys="id",  # type: ignore[arg-type]
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_empty_keys(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                Deduplicate(
                    batch=batch, keys=(),
                    _config=KnotConfig(id="d"),
                )
