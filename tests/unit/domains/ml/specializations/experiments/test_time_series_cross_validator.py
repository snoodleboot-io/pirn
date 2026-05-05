"""Unit tests for :class:`TimeSeriesCrossValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.time_series_cross_validator import (
    TimeSeriesCrossValidator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_n_splits_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="arima",
                    metrics=["mape"],
                    n_splits=1,
                    _config=KnotConfig(id="tscv"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="",
                    metrics=["mape"],
                    _config=KnotConfig(id="tscv"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="arima",
                    metrics=[],
                    _config=KnotConfig(id="tscv"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            TimeSeriesCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="arima",
                metrics=["mape"],
                n_splits=5,
                _config=KnotConfig(id="tscv"),
            )
        self.assertIsNotNone(t._store.get("tscv"))
