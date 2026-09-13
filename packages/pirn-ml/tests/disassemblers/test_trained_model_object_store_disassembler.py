"""Unit tests for :class:`TrainedModelObjectStoreDisassembler`."""

from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_ml.disassemblers.trained_model_object_store_disassembler import (
    TrainedModelObjectStoreDisassembler,
)
from pirn_ml.types.fitted_estimator import FittedEstimator
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.trained_model_payload import TrainedModelPayload

joblib = pytest.importorskip("joblib")


def _payload_param() -> Parameter:
    return Parameter("payload", object, _config=KnotConfig(id="payload"))


def _make() -> TrainedModelObjectStoreDisassembler:
    return TrainedModelObjectStoreDisassembler(
        payload=_payload_param(),
        _config=KnotConfig(id="disassembler"),
    )


def _payload(estimator: object) -> TrainedModelPayload:
    manifest = ModelManifest(
        model_id="m1",
        algorithm="rf",
        feature_names=(),
        target_name="",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    return TrainedModelPayload(
        metadata=manifest,
        data=FittedEstimator(estimator=estimator, algorithm="rf"),
    )


class TestTrainedModelObjectStoreDisassembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bytes(self) -> None:
        knot = _make()
        result = await knot.process(payload=_payload({"coef": [1.0]}))
        assert isinstance(result, bytes)

    async def test_serialised_bytes_round_trip_via_joblib(self) -> None:
        knot = _make()
        result = await knot.process(payload=_payload({"coef": [1.0, 2.0]}))
        restored = joblib.load(io.BytesIO(result))
        assert restored == {"coef": [1.0, 2.0]}

    async def test_rejects_non_payload(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="payload must be TrainedModelPayload"):
            await knot.process(payload="not-a-payload")  # type: ignore[arg-type]
