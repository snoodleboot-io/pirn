"""Tests for :class:`ShadowDeployer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.deployment.shadow_deployer import ShadowDeployer
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


def _make_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


class TestShadowDeployerHappyPath(unittest.IsolatedAsyncioTestCase):
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


class TestShadowDeployerProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ShadowDeployer:
        with Tapestry():
            sd = ShadowDeployer.__new__(ShadowDeployer)
            object.__setattr__(sd, "_config", KnotConfig(id="x"))
        return sd

    async def test_rejects_non_trained_model(self) -> None:
        sd = self._make_knot()
        lineage = RecordingLineageStore()
        with self.assertRaises((TypeError, ValueError)):
            await sd.process(
                model="not a model",  # type: ignore[arg-type]
                registry=lineage,
            )
