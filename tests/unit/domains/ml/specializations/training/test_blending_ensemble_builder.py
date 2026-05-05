"""Unit tests for :class:`BlendingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.blending_ensemble_builder import (
    BlendingEnsembleBuilder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_fewer_than_two_algorithms(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BlendingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    base_algorithms=["rf"],
                    metrics=["accuracy"],
                    _config=KnotConfig(id="beb"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BlendingEnsembleBuilder(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    base_algorithms=["rf", "xgb"],
                    metrics=[],
                    _config=KnotConfig(id="beb"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BlendingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                base_algorithms=["rf", "xgb"],
                metrics=["accuracy"],
                _config=KnotConfig(id="beb"),
            )
        self.assertIsNotNone(t._store.get("beb"))
