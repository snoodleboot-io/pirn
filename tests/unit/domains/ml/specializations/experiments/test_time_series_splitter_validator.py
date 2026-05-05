"""Unit tests for :class:`TimeSeriesSplitterValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.time_series_splitter_validator import (
    TimeSeriesSplitterValidator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_time_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesSplitterValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    time_column="",
                    algorithm="arima",
                    metrics=["mape"],
                    _config=KnotConfig(id="tssv"),
                )

    def test_rejects_n_splits_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesSplitterValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    time_column="ts",
                    algorithm="arima",
                    metrics=["mape"],
                    n_splits=1,
                    _config=KnotConfig(id="tssv"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            TimeSeriesSplitterValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                time_column="ts",
                algorithm="arima",
                metrics=["mape"],
                n_splits=5,
                _config=KnotConfig(id="tssv"),
            )
        self.assertIsNotNone(t._store.get("tssv"))
