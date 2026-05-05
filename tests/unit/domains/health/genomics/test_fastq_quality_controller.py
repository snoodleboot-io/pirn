"""Unit tests for :class:`FastqQualityController`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.fastq_quality_controller import (
    FastqQualityController,
)
from pirn.domains.health.types.genomics_record import GenomicsRecord
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string_path(self) -> None:
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            FastqQualityController(
                fastq_path=42,  # type: ignore[arg-type]
                sample_id="S1",
                _config=KnotConfig(id="q"),
            )

    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            FastqQualityController(
                fastq_path="",
                sample_id="S1",
                _config=KnotConfig(id="q"),
            )

    def test_rejects_empty_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            FastqQualityController(
                fastq_path="x.fq",
                sample_id="",
                _config=KnotConfig(id="q"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_genomics_record(self) -> None:
        with Tapestry() as t:
            FastqQualityController(
                fastq_path="x.fq",
                sample_id="S1",
                _config=KnotConfig(id="q"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["q"]
        assert isinstance(out, GenomicsRecord)
        assert out.sample_id == "S1"
