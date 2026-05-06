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


def _make_batch() -> DataBatch:
    rows = (
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
        {"id": 1, "name": "alice-dup"},
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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_keys_from_upstream_knot(self) -> None:
        @knot
        async def emit_keys() -> tuple:
            return ("id",)

        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            keys_knot = emit_keys(_config=KnotConfig(id="keys"))
            Deduplicate(
                batch=batch,
                keys=keys_knot,
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dedup"]
        assert out.row_count == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self) -> Deduplicate:
        @knot
        async def upstream() -> DataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return Deduplicate(batch=batch, keys=("id",), _config=KnotConfig(id="d"))

    async def test_rejects_string_keys_argument(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(batch=_make_batch(), keys="id")

    async def test_rejects_empty_keys(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(batch=_make_batch(), keys=())

    async def test_rejects_empty_string_key(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty string"):
            await k.process(batch=_make_batch(), keys=("",))
