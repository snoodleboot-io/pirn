"""Tests for :class:`DataDriftDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.data_drift_detector import (
    DataDriftDetector,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_reference() -> DataSplit:
    train = MLDataset(name="r:train", feature_names=("a", "b"), row_count=800)
    test = MLDataset(name="r:test", feature_names=("a", "b"), row_count=200)
    return DataSplit(train=train, test=test)


@knot
async def emit_current() -> DataSplit:
    train = MLDataset(name="c:train", feature_names=("a", "b"), row_count=900)
    test = MLDataset(name="c:test", feature_names=("a", "b"), row_count=100)
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_features(self) -> None:
        with Tapestry():
            ref = emit_reference(_config=KnotConfig(id="r"))
            cur = emit_current(_config=KnotConfig(id="c"))
            with pytest.raises(ValueError, match="features"):
                DataDriftDetector(
                    reference=ref,
                    current=cur,
                    features=(),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_negative_threshold(self) -> None:
        with Tapestry():
            ref = emit_reference(_config=KnotConfig(id="r"))
            cur = emit_current(_config=KnotConfig(id="c"))
            with pytest.raises(ValueError, match="psi_threshold"):
                DataDriftDetector(
                    reference=ref,
                    current=cur,
                    features=("a",),
                    psi_threshold=-0.1,
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_drift_report(self) -> None:
        with Tapestry() as t:
            ref = emit_reference(_config=KnotConfig(id="r"))
            cur = emit_current(_config=KnotConfig(id="c"))
            DataDriftDetector(
                reference=ref,
                current=cur,
                features=("a", "b"),
                psi_threshold=0.2,
                _config=KnotConfig(id="dd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["dd"]
        assert set(out["psi"].keys()) == {"a", "b"}
        assert set(out["ks_statistic"].keys()) == {"a", "b"}
        assert isinstance(out["drift_detected"], bool)
        assert isinstance(out["drifted_features"], list)
