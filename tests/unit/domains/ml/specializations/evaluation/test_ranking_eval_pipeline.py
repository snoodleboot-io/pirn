"""Unit tests for :class:`RankingEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.ranking_eval_pipeline import (
    RankingEvalPipeline,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_k_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RankingEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    k=0,
                    _config=KnotConfig(id="rp"),
                )

    def test_rejects_non_int_k(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                RankingEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    k=5.0,  # type: ignore[arg-type]
                    _config=KnotConfig(id="rp"),
                )

    def test_k_attribute_stored(self) -> None:
        with Tapestry():
            rp = RankingEvalPipeline(
                model=_KnotStub(_config=KnotConfig(id="m")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                k=20,
                _config=KnotConfig(id="rp"),
            )
        self.assertEqual(rp.k, 20)
