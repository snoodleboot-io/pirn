"""Unit tests for :class:`BiasDetector`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.bias_detector import BiasDetector
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


class _ModelSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ModelManifest:
        return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",), target_name="y")


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("a", "gender"), target_name="y", row_count=20)
        return SplitManifest(train=ds, test=ds)


def _make_knot() -> BiasDetector:
    with Tapestry():
        return BiasDetector(
            model=_ModelSource(_config=KnotConfig(id="m")),
            split=_SplitSource(_config=KnotConfig(id="s")),
            sensitive_columns=["gender"],
            _config=KnotConfig(id="bd"),
        )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_model(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                BiasDetector(
                    model="not-a-knot",  # type: ignore[arg-type]
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    sensitive_columns=["gender"],
                    _config=KnotConfig(id="bd"),
                )


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_sensitive_columns(self) -> None:
        k = _make_knot()
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        model = ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",), target_name="y")
        split = SplitManifest(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, sensitive_columns=[])


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eval_report(self) -> None:
        with Tapestry() as t:
            BiasDetector(
                model=_ModelSource(_config=KnotConfig(id="m")),
                split=_SplitSource(_config=KnotConfig(id="s")),
                sensitive_columns=["gender"],
                _config=KnotConfig(id="bd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
