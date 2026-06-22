"""Tests for :class:`DimensionalityReductionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.dimensionality_reduction_pipeline import (
    DimensionalityReductionPipeline,
)

from tests._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = DimensionalityReductionPipeline.__new__(DimensionalityReductionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                feature_names=("a",),
            )

    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = DimensionalityReductionPipeline.__new__(DimensionalityReductionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                feature_names=("a",),
                algorithm="lda",
            )

    async def test_rejects_zero_n_components(self) -> None:
        with Tapestry():
            k = DimensionalityReductionPipeline.__new__(DimensionalityReductionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                feature_names=("a",),
                algorithm="pca",
                n_components=0,
            )
