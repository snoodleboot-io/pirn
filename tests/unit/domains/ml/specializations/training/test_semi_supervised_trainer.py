"""Unit tests for :class:`SemiSupervisedTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.semi_supervised_trainer import (
    SemiSupervisedTrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_unlabeled_row_count(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                SemiSupervisedTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="rf",
                    unlabeled_row_count=-1,
                    metrics=["accuracy"],
                    _config=KnotConfig(id="sst"),
                )

    def test_rejects_non_int_unlabeled_row_count(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                SemiSupervisedTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="rf",
                    unlabeled_row_count=100.5,  # type: ignore[arg-type]
                    metrics=["accuracy"],
                    _config=KnotConfig(id="sst"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                SemiSupervisedTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="rf",
                    unlabeled_row_count=100,
                    metrics=[],
                    _config=KnotConfig(id="sst"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            SemiSupervisedTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="rf",
                unlabeled_row_count=500,
                metrics=["accuracy"],
                _config=KnotConfig(id="sst"),
            )
        self.assertIsNotNone(t._store.get("sst"))
