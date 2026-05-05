"""Unit tests for :class:`BiasDetector`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.bias_detector import BiasDetector
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


class _ModelSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> TrainedModel:
        return TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",), target_name="y")


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("a", "gender"), target_name="y", row_count=20)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_sensitive_columns(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BiasDetector(
                    model=_ModelSource(_config=KnotConfig(id="m")),
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    sensitive_columns=[],
                    _config=KnotConfig(id="bd"),
                )

    def test_rejects_non_knot_model(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                BiasDetector(
                    model="not-a-knot",  # type: ignore[arg-type]
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    sensitive_columns=["gender"],
                    _config=KnotConfig(id="bd"),
                )

    def test_sensitive_columns_stored(self) -> None:
        with Tapestry():
            bd = BiasDetector(
                model=_ModelSource(_config=KnotConfig(id="m")),
                split=_SplitSource(_config=KnotConfig(id="s")),
                sensitive_columns=["gender"],
                _config=KnotConfig(id="bd"),
            )
        self.assertEqual(bd.sensitive_columns, ("gender",))
