"""Tests for :class:`CollaborativeFilteringPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.collaborative_filtering_pipeline import (
    CollaborativeFilteringPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = CollaborativeFilteringPipeline.__new__(CollaborativeFilteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 2, 3.0)]),
                query="SELECT 1",
                user_column="user",
                item_column="item",
                rating_column="rating",
                algorithm="nmf",
            )

    async def test_rejects_zero_top_k(self) -> None:
        with Tapestry():
            k = CollaborativeFilteringPipeline.__new__(CollaborativeFilteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 2, 3.0)]),
                query="SELECT 1",
                user_column="user",
                item_column="item",
                rating_column="rating",
                top_k=0,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eval_report(self) -> None:
        rows = [(i % 5, i % 10, float(i % 5 + 1)) for i in range(50)]
        with Tapestry() as t:
            CollaborativeFilteringPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT user, item, rating FROM data",
                user_column="user",
                item_column="item",
                rating_column="rating",
                top_k=5,
                _config=KnotConfig(id="cf"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["cf"]
        assert isinstance(report, EvalReport)
