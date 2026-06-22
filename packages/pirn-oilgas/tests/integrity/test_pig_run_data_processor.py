"""Unit tests for :class:`PigRunDataProcessor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.integrity.pig_run_data_processor import PigRunDataProcessor


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, pipeline_id: str = "P1", run_path: str = "/x") -> PigRunDataProcessor:
        return PigRunDataProcessor(
            pipeline_id=pipeline_id,
            run_path=run_path,
            _config=KnotConfig(id="pr"),
        )

    async def test_rejects_empty_pipeline_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "pipeline_id"):
            await knot.process(pipeline_id="", run_path="/x")

    async def test_rejects_empty_run_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "run_path"):
            await knot.process(pipeline_id="P1", run_path="")

    async def test_returns_summary_dict(self) -> None:
        knot = self._make_knot()
        out = await knot.process(pipeline_id="P1", run_path="/x")
        assert out["pipeline_id"] == "P1"
        assert "feature_count" in out
