"""Unit tests for :class:`VEPAnnotator`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.vep_annotator import VEPAnnotator

_CFG = KnotConfig(id="a")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VEPAnnotator:
        return VEPAnnotator(
            vcf_path="in.vcf",
            cache_dir="c",
            output_vcf_path="out.vcf",
            _config=_CFG,
        )

    async def test_rejects_non_string(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "vcf_path"):
            await knot.process(vcf_path=42, cache_dir="c", output_vcf_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(vcf_path="", cache_dir="c", output_vcf_path="out")

    async def test_returns_annotated_path(self) -> None:
        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(vcf_path="in.vcf", cache_dir="c", output_vcf_path="out.vcf")
        assert out == "out.vcf"
