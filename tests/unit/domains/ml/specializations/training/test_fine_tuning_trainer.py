"""Unit tests for :class:`FineTuningTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.fine_tuning_trainer import (
    FineTuningTrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_pretrained_model_id(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FineTuningTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrained_model_id="",
                    algorithm="nn",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="ftt"),
                )

    def test_rejects_frozen_layers_negative(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FineTuningTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrained_model_id="base-model",
                    algorithm="nn",
                    metrics=["accuracy"],
                    frozen_layers=-1,
                    _config=KnotConfig(id="ftt"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FineTuningTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrained_model_id="base",
                    algorithm="nn",
                    metrics=[],
                    _config=KnotConfig(id="ftt"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FineTuningTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                pretrained_model_id="resnet50",
                algorithm="nn",
                metrics=["accuracy"],
                frozen_layers=5,
                _config=KnotConfig(id="ftt"),
            )
        self.assertIsNotNone(t._store.get("ftt"))
