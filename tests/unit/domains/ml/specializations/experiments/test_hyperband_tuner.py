"""Unit tests for :class:`HyperbandTuner`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.hyperband_tuner import HyperbandTuner


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            HyperbandTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="nn",
                search_space={"lr": [0.01, 0.1]},
                primary_metric="val_loss",
                max_configs=8,
                _config=KnotConfig(id="ht"),
            )
        self.assertIsNotNone(t._store.get("ht"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> HyperbandTuner:
        with Tapestry():
            return HyperbandTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="nn",
                search_space={"lr": [0.01]},
                primary_metric="val_loss",
                _config=KnotConfig(id="ht"),
            )

    async def test_rejects_max_configs_less_than_1(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="nn",
                search_space={"lr": [0.01]},
                primary_metric="val_loss",
                max_configs=0,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="",
                search_space={"lr": [0.01]},
                primary_metric="val_loss",
            )
