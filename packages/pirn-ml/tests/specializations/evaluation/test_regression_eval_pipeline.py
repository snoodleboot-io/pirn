"""Unit tests for :class:`RegressionEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.regression_eval_pipeline import (
    RegressionEvalPipeline,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            RegressionEvalPipeline(
                model=_KnotStub(_config=KnotConfig(id="m")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                _config=KnotConfig(id="rp"),
            )
        self.assertIsNotNone(t._store.get("rp"))
