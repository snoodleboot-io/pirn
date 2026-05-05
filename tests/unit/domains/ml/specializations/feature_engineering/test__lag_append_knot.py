"""Unit tests for :class:`_LagAppendKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering._lag_append_knot import (
    _LagAppendKnot,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("sales",), row_count=30)
        return DataSplit(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_lag_feature_names(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            _LagAppendKnot(
                split=src,
                time_column="date",
                columns=["sales"],
                lags=[1, 7],
                _config=KnotConfig(id="lag"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["lag"]
        self.assertIsInstance(split, DataSplit)
        self.assertIn("sales_lag_1", split.train.feature_names)
        self.assertIn("sales_lag_7", split.train.feature_names)
