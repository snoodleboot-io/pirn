"""Unit tests for :class:`SelfSupervisedPretrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.self_supervised_pretrainer import (
    SelfSupervisedPretrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_pretrain_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                SelfSupervisedPretrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrain_algorithm="",
                    finetune_algorithm="logistic",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="ssp"),
                )

    def test_rejects_empty_finetune_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                SelfSupervisedPretrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrain_algorithm="masked",
                    finetune_algorithm="",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="ssp"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                SelfSupervisedPretrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    pretrain_algorithm="masked",
                    finetune_algorithm="logistic",
                    metrics=[],
                    _config=KnotConfig(id="ssp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            SelfSupervisedPretrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                pretrain_algorithm="masked",
                finetune_algorithm="logistic",
                metrics=["accuracy"],
                _config=KnotConfig(id="ssp"),
            )
        self.assertIsNotNone(t._store.get("ssp"))
