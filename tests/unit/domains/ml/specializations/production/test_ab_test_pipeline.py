"""Unit tests for :class:`ABTestPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.production.ab_test_pipeline import ABTestPipeline
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_alpha_zero(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ABTestPipeline(
                    model_a=_KnotStub(_config=KnotConfig(id="a")),
                    model_b=_KnotStub(_config=KnotConfig(id="b")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    alpha=0.0,
                    _config=KnotConfig(id="ab"),
                )

    def test_rejects_invalid_alpha_one(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ABTestPipeline(
                    model_a=_KnotStub(_config=KnotConfig(id="a")),
                    model_b=_KnotStub(_config=KnotConfig(id="b")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    alpha=1.0,
                    _config=KnotConfig(id="ab"),
                )

    def test_rejects_empty_primary_metric(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ABTestPipeline(
                    model_a=_KnotStub(_config=KnotConfig(id="a")),
                    model_b=_KnotStub(_config=KnotConfig(id="b")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="",
                    _config=KnotConfig(id="ab"),
                )

    def test_primary_metric_attribute(self) -> None:
        with Tapestry():
            ab = ABTestPipeline(
                model_a=_KnotStub(_config=KnotConfig(id="a")),
                model_b=_KnotStub(_config=KnotConfig(id="b")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                primary_metric="accuracy",
                _config=KnotConfig(id="ab"),
            )
        self.assertEqual(ab.primary_metric, "accuracy")
