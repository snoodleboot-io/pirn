"""Unit tests for :class:`TimeSeriesEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.timeseries_eval_pipeline import (
    TimeSeriesEvalPipeline,
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
                TimeSeriesEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    time_column="",
                    _config=KnotConfig(id="ts"),
                )

    def test_rejects_non_string_time_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TimeSeriesEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    time_column=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="ts"),
                )

    def test_time_column_attribute_stored(self) -> None:
        with Tapestry():
            ts = TimeSeriesEvalPipeline(
                model=_KnotStub(_config=KnotConfig(id="m")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                time_column="timestamp",
                _config=KnotConfig(id="ts"),
            )
        self.assertEqual(ts.time_column, "timestamp")
