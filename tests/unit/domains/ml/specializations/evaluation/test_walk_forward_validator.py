"""Unit tests for :class:`WalkForwardValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.walk_forward_validator import (
    WalkForwardValidator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_dataset(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                WalkForwardValidator(
                    dataset="bad",  # type: ignore[arg-type]
                    time_column="ts",
                    train_window=10,
                    test_window=5,
                    algorithm="arima",
                    _config=KnotConfig(id="wfv"),
                )

    def test_rejects_train_window_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                WalkForwardValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    time_column="ts",
                    train_window=0,
                    test_window=5,
                    algorithm="arima",
                    _config=KnotConfig(id="wfv"),
                )

    def test_rejects_empty_time_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                WalkForwardValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    time_column="",
                    train_window=10,
                    test_window=5,
                    algorithm="arima",
                    _config=KnotConfig(id="wfv"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                WalkForwardValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    time_column="ts",
                    train_window=10,
                    test_window=5,
                    algorithm="",
                    _config=KnotConfig(id="wfv"),
                )

    def test_n_steps_attribute_stored(self) -> None:
        with Tapestry():
            wfv = WalkForwardValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                time_column="ts",
                train_window=10,
                test_window=5,
                algorithm="arima",
                n_steps=3,
                _config=KnotConfig(id="wfv"),
            )
        self.assertEqual(wfv.n_steps, 3)
