"""Tests for :class:`FrequencyEncoder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.frequency_encoder import (
    FrequencyEncoder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("city",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("city",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_categorical_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="categorical_column"):
                FrequencyEncoder(
                    split=split,
                    categorical_column="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_negative_default_frequency(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="default_frequency"):
                FrequencyEncoder(
                    split=split,
                    categorical_column="city",
                    default_frequency=-0.1,
                    _config=KnotConfig(id="bad"),
                )

    def test_stores_default_frequency(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            enc = FrequencyEncoder(
                split=split,
                categorical_column="city",
                default_frequency=0.01,
                _config=KnotConfig(id="fe"),
            )
        assert enc.default_frequency == pytest.approx(0.01)


class TestHappyPath:
    async def test_emits_freq_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FrequencyEncoder(
                split=split,
                categorical_column="city",
                _config=KnotConfig(id="fe"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fe"]
        assert isinstance(out, DataSplit)
        assert "freq_encoded" in out.train.name
