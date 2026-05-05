"""Unit tests for :class:`StackingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.stacking_ensemble_builder import (
    StackingEnsembleBuilder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_fewer_than_two_base_algorithms(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                StackingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    base_algorithms=["rf"],
                    meta_algorithm="logistic",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="seb"),
                )

    def test_rejects_empty_meta_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                StackingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    base_algorithms=["rf", "xgb"],
                    meta_algorithm="",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="seb"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                StackingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    base_algorithms=["rf", "xgb"],
                    meta_algorithm="logistic",
                    metrics=[],
                    _config=KnotConfig(id="seb"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            StackingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                base_algorithms=["rf", "xgb"],
                meta_algorithm="logistic",
                metrics=["accuracy"],
                _config=KnotConfig(id="seb"),
            )
        self.assertIsNotNone(t._store.get("seb"))
