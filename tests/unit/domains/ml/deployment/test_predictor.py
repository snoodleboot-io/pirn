"""Tests for :class:`Predictor`."""

from __future__ import annotations

from typing import Any, Iterable, Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.deployment.predictor import Predictor
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)
from tests.unit.domains.ml._stubs.recording_object_store import (
    RecordingObjectStore,
)


@knot
async def emit_features() -> Iterable[Mapping[str, Any]]:
    return [{"a": 1.0}, {"a": 2.0}, {"a": 3.0}]


class TestPredictorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_one_prediction_per_row(self) -> None:
        lineage = RecordingLineageStore()
        store = RecordingObjectStore()
        with Tapestry() as t:
            features = emit_features(_config=KnotConfig(id="feat"))
            Predictor(
                model_id="m1",
                features=features,
                lineage=lineage,
                store=store,
                _config=KnotConfig(id="pred"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["pred"]
        assert isinstance(out, list)
        assert len(out) == 3
        assert lineage.fetches == ["m1"]


class TestPredictorProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> Predictor:
        with Tapestry():
            p = Predictor.__new__(Predictor)
            object.__setattr__(p, "_config", KnotConfig(id="x"))
        return p

    async def test_rejects_empty_string_model_id(self) -> None:
        p = self._make_knot()
        lineage = RecordingLineageStore()
        store = RecordingObjectStore()
        with self.assertRaises((TypeError, ValueError)):
            await p.process(
                model_id="",
                features=[{"a": 1.0}],
                lineage=lineage,
                store=store,
            )
