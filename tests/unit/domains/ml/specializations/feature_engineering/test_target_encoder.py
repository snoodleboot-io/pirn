"""Unit tests for :class:`TargetEncoder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering.target_encoder import (
    TargetEncoder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_categorical_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TargetEncoder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    categorical_column="",
                    target_column="y",
                    _config=KnotConfig(id="te"),
                )

    def test_rejects_negative_smoothing(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TargetEncoder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    categorical_column="cat",
                    target_column="y",
                    smoothing=-1.0,
                    _config=KnotConfig(id="te"),
                )

    def test_rejects_empty_target_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TargetEncoder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    categorical_column="cat",
                    target_column="",
                    _config=KnotConfig(id="te"),
                )

    def test_smoothing_attribute(self) -> None:
        with Tapestry():
            te = TargetEncoder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                categorical_column="cat",
                target_column="y",
                smoothing=2.0,
                _config=KnotConfig(id="te"),
            )
        self.assertAlmostEqual(te.smoothing, 2.0)
