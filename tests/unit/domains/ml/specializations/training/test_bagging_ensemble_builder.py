"""Unit tests for :class:`BaggingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.bagging_ensemble_builder import (
    BaggingEnsembleBuilder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_n_estimators_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BaggingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="dt",
                    n_estimators=1,
                    metrics=["accuracy"],
                    _config=KnotConfig(id="beb"),
                )

    def test_rejects_invalid_task(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BaggingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="dt",
                    task="clustering",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="beb"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BaggingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="beb"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BaggingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="dt",
                n_estimators=5,
                task="classification",
                metrics=["accuracy"],
                _config=KnotConfig(id="beb"),
            )
        self.assertIsNotNone(t._store.get("beb"))
