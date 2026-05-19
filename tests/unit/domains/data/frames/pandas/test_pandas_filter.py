"""Tests for :class:`PandasFilter`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.frames.pandas.pandas_filter import PandasFilter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


def _users_batch() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


class TestPandasFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_rows_matching_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasFilter(
                batch=batch,
                predicate=lambda df: df["active"],
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["active"]
        assert tuple(out.frame["id"].tolist()) == (1, 3)

    async def test_compound_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasFilter(
                batch=batch,
                predicate=lambda df: (df["region"] == "EU") & df["active"],
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["active_eu"]
        assert tuple(out.frame["id"].tolist()) == (1,)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_predicate() -> object:
            return lambda df: df["active"]

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            pred_knot = emit_predicate(_config=KnotConfig(id="pred"))
            PandasFilter(
                batch=batch,
                predicate=pred_knot,
                _config=KnotConfig(id="filtered"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["filtered"]
        assert tuple(out.frame["id"].tolist()) == (1, 3)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PandasFilter:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PandasFilter(
                batch=batch,
                predicate=lambda df: df["active"],
                _config=KnotConfig(id="f"),
                **kwargs,
            )

    async def test_rejects_non_callable_predicate(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_users_batch(),
                predicate="active == True",
            )
