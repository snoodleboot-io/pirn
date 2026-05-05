"""Unit tests for :class:`KFoldCrossValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.kfold_cross_validator import (
    KFoldCrossValidator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_k_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                KFoldCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="rf",
                    metrics=["accuracy"],
                    k=1,
                    _config=KnotConfig(id="kf"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                KFoldCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="rf",
                    metrics=[],
                    _config=KnotConfig(id="kf"),
                )

    def test_rejects_non_int_k(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                KFoldCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="rf",
                    metrics=["accuracy"],
                    k=5.0,  # type: ignore[arg-type]
                    _config=KnotConfig(id="kf"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            KFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                k=5,
                _config=KnotConfig(id="kf"),
            )
        self.assertIsNotNone(t._store.get("kf"))
