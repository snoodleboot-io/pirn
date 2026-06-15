"""Unit tests for :class:`GVCFCombiner`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn_health.genomics.gvcf_combiner import GVCFCombiner

_CFG = KnotConfig(id="c")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GVCFCombiner:
        return GVCFCombiner(
            gvcf_paths=["a.gvcf", "b.gvcf"],
            reference_path="ref.fa",
            output_gvcf_path="out.gvcf",
            _config=_CFG,
        )

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "gvcf_paths"):
            await knot.process(gvcf_paths=42, reference_path="ref", output_gvcf_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(gvcf_paths=[], reference_path="ref", output_gvcf_path="out")

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(gvcf_paths=[""], reference_path="ref", output_gvcf_path="out")

    async def test_returns_combined_path(self) -> None:
        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(gvcf_paths=["a.gvcf", "b.gvcf"], reference_path="ref.fa", output_gvcf_path="out.gvcf")
        assert out == "out.gvcf"
