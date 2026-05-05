"""Unit tests for :class:`RegressionEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.regression_eval_pipeline import (
    RegressionEvalPipeline,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_model(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                RegressionEvalPipeline(
                    model="bad",  # type: ignore[arg-type]
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    _config=KnotConfig(id="rp"),
                )

    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                RegressionEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="rp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            RegressionEvalPipeline(
                model=_KnotStub(_config=KnotConfig(id="m")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                _config=KnotConfig(id="rp"),
            )
        self.assertIsNotNone(t._store.get("rp"))
