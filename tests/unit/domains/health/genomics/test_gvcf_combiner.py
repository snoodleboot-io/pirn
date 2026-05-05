"""Unit tests for :class:`GVCFCombiner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.gvcf_combiner import GVCFCombiner
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "gvcf_paths"):
            GVCFCombiner(
                gvcf_paths=42,  # type: ignore[arg-type]
                reference_path="ref",
                output_gvcf_path="out",
                _config=KnotConfig(id="c"),
            )

    def test_rejects_empty_sequence(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            GVCFCombiner(
                gvcf_paths=[],
                reference_path="ref",
                output_gvcf_path="out",
                _config=KnotConfig(id="c"),
            )

    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            GVCFCombiner(
                gvcf_paths=[""],
                reference_path="ref",
                output_gvcf_path="out",
                _config=KnotConfig(id="c"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_combined_path(self) -> None:
        with Tapestry() as t:
            GVCFCombiner(
                gvcf_paths=["a.gvcf", "b.gvcf"],
                reference_path="ref.fa",
                output_gvcf_path="out.gvcf",
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert out == "out.gvcf"
