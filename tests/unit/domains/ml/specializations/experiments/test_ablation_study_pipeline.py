"""Unit tests for :class:`AblationStudyPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.ablation_study_pipeline import (
    AblationStudyPipeline,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                AblationStudyPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="",
                    feature_groups={"g1": ["a"]},
                    metrics=["accuracy"],
                    _config=KnotConfig(id="asp"),
                )

    def test_rejects_empty_feature_groups(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                AblationStudyPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="logistic",
                    feature_groups={},
                    metrics=["accuracy"],
                    _config=KnotConfig(id="asp"),
                )

    def test_rejects_reserved_full_key(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                AblationStudyPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="logistic",
                    feature_groups={"full": ["a"]},
                    metrics=["accuracy"],
                    _config=KnotConfig(id="asp"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                AblationStudyPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="logistic",
                    feature_groups={"g1": ["a"]},
                    metrics=[],
                    _config=KnotConfig(id="asp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            AblationStudyPipeline(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="logistic",
                feature_groups={"g1": ["a", "b"]},
                metrics=["accuracy"],
                _config=KnotConfig(id="asp"),
            )
        self.assertIsNotNone(t._store.get("asp"))
