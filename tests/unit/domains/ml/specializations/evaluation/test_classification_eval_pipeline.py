"""Unit tests for :class:`ClassificationEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.classification_eval_pipeline import (
    ClassificationEvalPipeline,
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
                ClassificationEvalPipeline(
                    model="not-a-knot",  # type: ignore[arg-type]
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    _config=KnotConfig(id="ep"),
                )

    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ClassificationEvalPipeline(
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    split="not-a-knot",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ep"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ClassificationEvalPipeline(
                model=_KnotStub(_config=KnotConfig(id="m")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                _config=KnotConfig(id="ep"),
            )
        self.assertIsNotNone(t._store.get("ep"))
