"""Unit tests for :class:`StructuralVariantDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.structural_variant_detector import (
    StructuralVariantDetector,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_bam(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            StructuralVariantDetector(
                bam_path="",
                reference_path="ref",
                sample_id="S1",
                _config=KnotConfig(id="d"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_tuple(self) -> None:
        with Tapestry() as t:
            StructuralVariantDetector(
                bam_path="in.bam",
                reference_path="ref.fa",
                sample_id="S1",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, tuple)
