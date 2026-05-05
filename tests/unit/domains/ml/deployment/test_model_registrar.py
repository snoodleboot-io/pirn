"""Tests for :class:`ModelRegistrar`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.deployment.model_registrar import ModelRegistrar
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)
from tests.unit.domains.ml._stubs.recording_object_store import (
    RecordingObjectStore,
)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


@knot
async def emit_serialized() -> bytes:
    return b"serialized-bytes"


class TestModelRegistrarHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_writes_to_lineage_and_object_store(self) -> None:
        lineage = RecordingLineageStore()
        store = RecordingObjectStore()
        with Tapestry() as t:
            serialized = emit_serialized(_config=KnotConfig(id="ser"))
            model = emit_model(_config=KnotConfig(id="model"))
            ModelRegistrar(
                serialized=serialized,
                model=model,
                lineage=lineage,
                store=store,
                _config=KnotConfig(id="reg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["reg"] == "m1"
        assert "models/m1.bin" in store.objects
        assert store.objects["models/m1.bin"] == b"serialized-bytes"
        assert lineage.events
        event_type, payload = lineage.events[0]
        assert event_type == "model_registered"
        assert payload["model_id"] == "m1"


class TestModelRegistrarConstruction(unittest.TestCase):
    def test_rejects_non_lineage(self) -> None:
        store = RecordingObjectStore()
        with Tapestry():
            serialized = emit_serialized(_config=KnotConfig(id="ser"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(TypeError, "LineageStore"):
                ModelRegistrar(
                    serialized=serialized,
                    model=model,
                    lineage="not a lineage",  # type: ignore[arg-type]
                    store=store,
                    _config=KnotConfig(id="bad"),
                )
