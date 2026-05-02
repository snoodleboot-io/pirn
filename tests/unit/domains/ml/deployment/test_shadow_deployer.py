"""Tests for :class:`ShadowDeployer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.deployment.shadow_deployer import ShadowDeployer
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


class TestShadowDeployerHappyPath:
    async def test_records_shadow_deployment(self) -> None:
        lineage = RecordingLineageStore()
        with Tapestry() as t:
            model = emit_model(_config=KnotConfig(id="model"))
            ShadowDeployer(
                model=model,
                registry=lineage,
                _config=KnotConfig(id="shadow"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        deployment_id = result.outputs["shadow"]
        assert deployment_id.startswith("shadow:")
        event_type, payload = lineage.events[0]
        assert event_type == "shadow_deployment"
        assert payload["model_id"] == "m1"


class TestShadowDeployerConstruction:
    def test_rejects_non_registry(self) -> None:
        with Tapestry():
            model = emit_model(_config=KnotConfig(id="model"))
            with pytest.raises(TypeError, match="LineageStore"):
                ShadowDeployer(
                    model=model,
                    registry="not a lineage",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )
