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


def _make_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


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


class TestModelRegistrarProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ModelRegistrar:
        with Tapestry():
            reg = ModelRegistrar.__new__(ModelRegistrar)
            object.__setattr__(reg, "_config", KnotConfig(id="x"))
        return reg

    async def test_rejects_non_bytes_serialized(self) -> None:
        reg = self._make_knot()
        store = RecordingObjectStore()
        lineage = RecordingLineageStore()
        with self.assertRaises((TypeError, ValueError)):
            await reg.process(
                serialized="not bytes",  # type: ignore[arg-type]
                model=_make_model(),
                lineage=lineage,
                store=store,
            )

    async def test_rejects_non_trained_model(self) -> None:
        reg = self._make_knot()
        store = RecordingObjectStore()
        lineage = RecordingLineageStore()
        with self.assertRaises((TypeError, ValueError)):
            await reg.process(
                serialized=b"bytes",
                model="not a model",  # type: ignore[arg-type]
                lineage=lineage,
                store=store,
            )
