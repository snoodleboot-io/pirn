"""Unit tests for :class:`MotionCorrector`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.motion_corrector import MotionCorrector

_CFG = KnotConfig(id="m")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MotionCorrector:
        return MotionCorrector(nifti_path="in.nii.gz", output_nifti_path="mc.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_nifti_path="out")

    async def test_returns_corrected_path(self) -> None:
        knot = self._make_knot()
        mock_ants = MagicMock()
        mock_ants.image_read.return_value = MagicMock()
        mock_ants.motion_correction.return_value = {"motion_corrected": MagicMock()}
        with patch("pirn.domains.health.mri.motion_corrector.ants", mock_ants), \
             patch("pirn.domains.health.mri.motion_corrector._HAS_ANTS", True):
            out = await knot.process(nifti_path="in.nii.gz", output_nifti_path="mc.nii.gz")
        assert out == "mc.nii.gz"
