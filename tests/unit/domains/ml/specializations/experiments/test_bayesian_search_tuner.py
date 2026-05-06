"""Unit tests for :class:`BayesianSearchTuner`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.bayesian_search_tuner import (
    BayesianSearchTuner,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BayesianSearchTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="xgboost",
                search_space={"lr": [0.01, 0.1]},
                primary_metric="accuracy",
                n_trials=30,
                _config=KnotConfig(id="bt"),
            )
        self.assertIsNotNone(t._store.get("bt"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BayesianSearchTuner:
        with Tapestry():
            return BayesianSearchTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="xgboost",
                search_space={"lr": [0.01, 0.1]},
                primary_metric="accuracy",
                _config=KnotConfig(id="bt"),
            )

    async def test_rejects_empty_search_space(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="xgboost",
                search_space={},
                primary_metric="accuracy",
            )

    async def test_rejects_n_trials_less_than_1(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="xgboost",
                search_space={"lr": [0.01, 0.1]},
                primary_metric="accuracy",
                n_trials=0,
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="xgboost",
                search_space={"lr": [0.01]},
                primary_metric="",
            )
