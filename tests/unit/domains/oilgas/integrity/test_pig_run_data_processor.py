"""Unit tests for :class:`PigRunDataProcessor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.pig_run_data_processor import PigRunDataProcessor
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_pipeline_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "pipeline_id"):
            PigRunDataProcessor(
                pipeline_id="",
                run_path="/x",
                _config=KnotConfig(id="pr"),
            )

    def test_rejects_empty_run_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "run_path"):
            PigRunDataProcessor(
                pipeline_id="P1",
                run_path="",
                _config=KnotConfig(id="pr"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_summary_dict(self) -> None:
        with Tapestry() as t:
            PigRunDataProcessor(
                pipeline_id="P1",
                run_path="/x",
                _config=KnotConfig(id="pr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pr"]
        assert out["pipeline_id"] == "P1"
        assert "feature_count" in out
