"""Unit tests for :class:`FrequencyEncoder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering.frequency_encoder import (
    FrequencyEncoder,
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
                FrequencyEncoder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    categorical_column="",
                    _config=KnotConfig(id="fe"),
                )

    def test_rejects_negative_default_frequency(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FrequencyEncoder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    categorical_column="cat",
                    default_frequency=-0.1,
                    _config=KnotConfig(id="fe"),
                )

    def test_default_frequency_attribute(self) -> None:
        with Tapestry():
            fe = FrequencyEncoder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                categorical_column="cat",
                default_frequency=0.05,
                _config=KnotConfig(id="fe"),
            )
        self.assertAlmostEqual(fe.default_frequency, 0.05)
