"""Unit tests for :class:`CorticalThicknessEstimator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.cortical_thickness_estimator import CorticalThicknessEstimator

_CFG = KnotConfig(id="c")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CorticalThicknessEstimator:
        return CorticalThicknessEstimator(t1_nifti_path="x", regions=["frontal"], _config=_CFG)

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(t1_nifti_path="", regions=[])

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "regions"):
            await knot.process(t1_nifti_path="x", regions=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_region(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(t1_nifti_path="x", regions=[1])  # type: ignore[list-item]

    async def test_returns_per_region_mapping(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(t1_nifti_path="x", regions=["frontal", "parietal"])
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"frontal", "parietal"}
