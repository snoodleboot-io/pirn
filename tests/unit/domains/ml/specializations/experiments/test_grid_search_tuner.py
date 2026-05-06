"""Unit tests for :class:`GridSearchTuner`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.grid_search_tuner import (
    GridSearchTuner,
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
            GridSearchTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="logistic",
                search_space={"C": [0.1, 1.0]},
                primary_metric="accuracy",
                _config=KnotConfig(id="gs"),
            )
        self.assertIsNotNone(t._store.get("gs"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GridSearchTuner:
        with Tapestry():
            return GridSearchTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="logistic",
                search_space={"C": [0.1, 1.0]},
                primary_metric="accuracy",
                _config=KnotConfig(id="gs"),
            )

    async def test_rejects_empty_search_space(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="logistic",
                search_space={},
                primary_metric="accuracy",
            )

    async def test_rejects_empty_algorithm(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="",
                search_space={"C": [0.1, 1.0]},
                primary_metric="accuracy",
            )
