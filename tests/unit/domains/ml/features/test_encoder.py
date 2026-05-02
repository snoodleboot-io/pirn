"""Tests for :class:`Encoder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.encoder import Encoder
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("region",), row_count=10)
    test = MLDataset(name="d:test", feature_names=("region",), row_count=5)
    return DataSplit(train=train, test=test)


class TestEncoderHappyPath:
    async def test_emits_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            Encoder(
                split=split,
                columns=("region",),
                method="onehot",
                _config=KnotConfig(id="enc"),
            )
        result = await t.run(RunRequest())
        out: DataSplit = result.outputs["enc"]
        assert out.train.name.endswith(":encoded_onehot")


class TestEncoderConstruction:
    def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="columns must be non-empty"):
                Encoder(
                    split=split,
                    columns=(),
                    _config=KnotConfig(id="bad"),
                )
