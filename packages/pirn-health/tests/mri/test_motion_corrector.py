"""Unit tests for :class:`MotionCorrector`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_health.mri.motion_corrector import MotionCorrector

_CFG = KnotConfig(id="m")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MotionCorrector:
        return MotionCorrector(nifti_path="in.nii.gz", output_nifti_path="mc.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_nifti_path="out")

    async def test_returns_corrected_path_3d(self) -> None:
        """3-D volume passes through unchanged."""
        knot = self._make_knot()
        mock_img = MagicMock()
        mock_img.dataobj = np.zeros((4, 4, 4))
        mock_img.affine = np.eye(4)
        mock_img.header = MagicMock()

        mock_nib = MagicMock()
        mock_nib.load.return_value = mock_img

        modules = {
            "nibabel": mock_nib,
            "dipy.align.imaffine": MagicMock(),
            "dipy.align.transforms": MagicMock(),
        }

        with patch.object(
            OptionalDependency,
            "require",
            side_effect=lambda module, **_: modules[module],
        ):
            out = await knot.process(nifti_path="in.nii.gz", output_nifti_path="mc.nii.gz")
        assert out == "mc.nii.gz"

    async def test_raises_without_dipy(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"dipy.align.imaffine": None}):
            with self.assertRaisesRegex(ImportError, "pirn-health\\[mri\\]"):
                await knot.process(nifti_path="in.nii.gz", output_nifti_path="mc.nii.gz")
