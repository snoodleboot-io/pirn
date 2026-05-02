"""Tests for :class:`ModelSerializer`."""

from __future__ import annotations

import json

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.deployment.model_serializer import ModelSerializer
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        hyperparameters={"n_estimators": 50},
        feature_names=("a",),
        target_name="y",
    )


class TestModelSerializerHappyPath:
    async def test_emits_json_bytes(self) -> None:
        with Tapestry() as t:
            model = emit_model(_config=KnotConfig(id="model"))
            ModelSerializer(
                model=model,
                format="json",
                _config=KnotConfig(id="ser"),
            )
        result = await t.run(RunRequest())
        out: bytes = result.outputs["ser"]
        assert isinstance(out, bytes)
        decoded = json.loads(out.decode("utf-8"))
        assert decoded["model_id"] == "m1"
        assert decoded["format"] == "json"


class TestModelSerializerConstruction:
    def test_rejects_unknown_format(self) -> None:
        with Tapestry():
            model = emit_model(_config=KnotConfig(id="model"))
            with pytest.raises(ValueError, match="format must be"):
                ModelSerializer(
                    model=model,
                    format="bogus",
                    _config=KnotConfig(id="bad"),
                )
