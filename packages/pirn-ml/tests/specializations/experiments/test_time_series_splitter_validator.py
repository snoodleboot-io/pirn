"""Unit tests for :class:`TimeSeriesSplitterValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.time_series_splitter_validator import (
    TimeSeriesSplitterValidator,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_validator() -> TimeSeriesSplitterValidator:
    with Tapestry():
        stub = _KnotStub(_config=KnotConfig(id="d"))
        return TimeSeriesSplitterValidator(
            dataset=stub,
            time_column="ts",
            algorithm="arima",
            metrics=["mape"],
            n_splits=5,
            _config=KnotConfig(id="tssv"),
        )


class TestConstruction(unittest.TestCase):
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


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_column(self) -> None:
        validator = _make_validator()
        from pirn_ml.types.dataset_manifest import DatasetManifest

        ds = DatasetManifest(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=20,
            source_uri="memory://ds",
        )
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                time_column="",
                algorithm="arima",
                metrics=["mape"],
                n_splits=5,
            )

    async def test_rejects_n_splits_less_than_2(self) -> None:
        validator = _make_validator()
        from pirn_ml.types.dataset_manifest import DatasetManifest

        ds = DatasetManifest(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=20,
            source_uri="memory://ds",
        )
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                time_column="ts",
                algorithm="arima",
                metrics=["mape"],
                n_splits=1,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        from pirn_ml.types.dataset_manifest import DatasetManifest

        ds = DatasetManifest(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=20,
            source_uri="memory://ds",
        )
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                time_column="ts",
                algorithm="",
                metrics=["mape"],
                n_splits=5,
            )

    async def test_rejects_empty_metrics(self) -> None:
        validator = _make_validator()
        from pirn_ml.types.dataset_manifest import DatasetManifest

        ds = DatasetManifest(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=20,
            source_uri="memory://ds",
        )
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                time_column="ts",
                algorithm="arima",
                metrics=[],
                n_splits=5,
            )
