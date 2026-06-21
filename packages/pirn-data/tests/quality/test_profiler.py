"""Tests for :class:`pirn_data.quality.profiler.Profiler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.data_profile import DataProfile
from pirn_data.data_schema import DataSchema
from pirn_data.quality.profiler import Profiler


@knot
async def emit_users() -> DataBatch:
    schema = DataSchema(columns={"id": int, "name": str, "region": str})
    rows = (
        {"id": 1, "name": "alice", "region": "EU"},
        {"id": 2, "name": "bob",   "region": "EU"},
        {"id": 3, "name": "alice", "region": "US"},
        {"id": 4, "name": None,    "region": "US"},
    )
    return DataBatch(rows=rows, schema=schema)


class TestProfiler(unittest.IsolatedAsyncioTestCase):
    async def test_emits_profile_with_row_and_column_counts(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        assert profile.row_count == 4
        assert profile.column_count == 3

    async def test_per_column_null_count(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        name_col = profile.column("name")
        assert name_col is not None
        assert name_col.null_count == 1
        assert name_col.observed_count == 4

    async def test_per_column_distinct_count(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        name_col = profile.column("name")
        assert name_col is not None
        assert name_col.distinct_count == 2
        region_col = profile.column("region")
        assert region_col is not None
        assert region_col.distinct_count == 2

    async def test_min_max_for_numeric_column(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        id_col = profile.column("id")
        assert id_col is not None
        assert id_col.min_value == 1
        assert id_col.max_value == 4

    async def test_top_value(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        name_col = profile.column("name")
        assert name_col is not None
        assert name_col.top_value == "alice"
        assert name_col.top_value_count == 2

    async def test_columns_filter_limits_profile_to_subset(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            Profiler(
                batch=batch, columns=("region",),
                _config=KnotConfig(id="profile"),
            )
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        assert profile.column_count == 1
        assert profile.column("region") is not None
        assert profile.column("name") is None

    async def test_empty_batch_yields_empty_profile(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        with Tapestry() as t:
            batch = empty(_config=KnotConfig(id="batch"))
            Profiler(batch=batch, _config=KnotConfig(id="profile"))
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        assert profile.row_count == 0
        assert profile.column_count == 0


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_columns_from_upstream_knot(self) -> None:
        @knot
        async def emit_columns() -> tuple:
            return ("region",)

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="batch"))
            cols_knot = emit_columns(_config=KnotConfig(id="cols"))
            Profiler(
                batch=batch, columns=cols_knot,
                _config=KnotConfig(id="profile"),
            )
        result = await t.run(RunRequest())
        profile: DataProfile = result.outputs["profile"]
        assert profile.column_count == 1
        assert profile.column("region") is not None
        assert profile.column("name") is None


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> Profiler:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return Profiler(batch=batch, _config=KnotConfig(id="p"), **kwargs)

    async def test_rejects_non_string_columns(self) -> None:
        k = self._make_knot(columns=("ok", 7))  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "strings"):
            await k.process(batch=DataBatch(), columns=("ok", 7))
