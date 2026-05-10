"""Tests for :class:`FullTrainDeployPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.full_train_deploy_pipeline import (
    FullTrainDeployPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)
from tests.unit.domains.ml._stubs.recording_object_store import (
    RecordingObjectStore,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_query(self) -> None:
        with Tapestry():
            k = FullTrainDeployPipeline.__new__(FullTrainDeployPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1,), (2,)]),
                query="",
                name="house-prices",
                feature_names=("a",),
                target_name="y",
                algorithm="logistic",
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=("accuracy",),
            )

    async def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            k = FullTrainDeployPipeline.__new__(FullTrainDeployPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1,)]),
                query="SELECT 1",
                name="model",
                feature_names=("a",),
                target_name="y",
                algorithm="logistic",
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=(),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_id_and_eval_report(self) -> None:
        rows = [(1.0, 0), (2.0, 1), (3.0, 0), (4.0, 1), (5.0, 0)] * 4
        lineage = RecordingLineageStore()
        store = RecordingObjectStore()
        with Tapestry() as t:
            FullTrainDeployPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                name="house-prices",
                feature_names=("a",),
                target_name="y",
                algorithm="logistic",
                lineage=lineage,
                store=store,
                metrics=("accuracy", "f1"),
                _config=KnotConfig(id="train-deploy"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["train-deploy"]
        assert isinstance(out["model_id"], str)
        assert out["model_id"].startswith("logistic:")
        assert isinstance(out["eval_report"], EvalReportPayload)
        # Model registered with lineage + object store
        assert any(event[0] == "model_registered" for event in lineage.events)
        assert any(
            key.startswith("models/") for key in store.put_calls
        )
