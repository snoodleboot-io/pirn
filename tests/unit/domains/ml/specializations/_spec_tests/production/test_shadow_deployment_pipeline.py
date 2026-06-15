"""Tests for :class:`ShadowDeploymentPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.shadow_deployment_pipeline import (
    ShadowDeploymentPipeline,
)
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)


@knot
async def emit_champion() -> ModelManifest:
    return ModelManifest(
        model_id="champ",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


@knot
async def emit_challenger() -> ModelManifest:
    return ModelManifest(
        model_id="chall",
        algorithm="gbdt",
        feature_names=("a",),
        target_name="y",
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_lineage_store(self) -> None:
        with Tapestry():
            champion = emit_champion(_config=KnotConfig(id="champ"))
            challenger = emit_challenger(_config=KnotConfig(id="chall"))
            with self.assertRaisesRegex(TypeError, "lineage"):
                ShadowDeploymentPipeline(
                    champion=champion,
                    challenger=challenger,
                    lineage="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_records_divergence_event(self) -> None:
        lineage = RecordingLineageStore()
        with Tapestry() as t:
            champion = emit_champion(_config=KnotConfig(id="champ"))
            challenger = emit_challenger(_config=KnotConfig(id="chall"))
            ShadowDeploymentPipeline(
                champion=champion,
                challenger=challenger,
                lineage=lineage,
                _config=KnotConfig(id="shadow"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["shadow"]
        assert out["champion_deployment_id"].startswith("shadow:")
        assert out["challenger_deployment_id"].startswith("shadow:")
        assert out["divergence_id"].startswith("divergence:")
        recorded_event_types = [event[0] for event in lineage.events]
        assert recorded_event_types.count("shadow_deployment") == 2
        assert recorded_event_types.count("shadow_divergence") == 1
