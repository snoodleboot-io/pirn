"""Unit tests for :class:`LagFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering.lag_feature_generator import (
    LagFeatureGenerator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_columns(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                LagFeatureGenerator(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    time_column="date",
                    columns=[],
                    _config=KnotConfig(id="lfg"),
                )

    def test_rejects_empty_time_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                LagFeatureGenerator(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    time_column="",
                    columns=["sales"],
                    _config=KnotConfig(id="lfg"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            LagFeatureGenerator(
                split=_KnotStub(_config=KnotConfig(id="s")),
                time_column="date",
                columns=["sales"],
                lags=[1, 7],
                _config=KnotConfig(id="lfg"),
            )
        self.assertIsNotNone(t._store.get("lfg"))
