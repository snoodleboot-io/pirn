"""Unit tests for :class:`BiasFieldCorrector`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig

from pirn_health.health_optional_dependency import HealthOptionalDependency
from pirn_health.mri.bias_field_corrector import BiasFieldCorrector

_CFG = KnotConfig(id="b")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BiasFieldCorrector:
        return BiasFieldCorrector(
            nifti_path="in.nii.gz", output_nifti_path="out.nii.gz", _config=_CFG
        )

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_nifti_path="out.nii.gz")

    async def test_returns_corrected_path(self) -> None:
        knot = self._make_knot()
        mock_sitk = MagicMock()
        mock_sitk.sitkFloat32 = 8
        with patch.object(
            HealthOptionalDependency,
            "require",
            side_effect=lambda module, **_: {"SimpleITK": mock_sitk}[module],
        ):
            out = await knot.process(nifti_path="in.nii.gz", output_nifti_path="out.nii.gz")
        assert out == "out.nii.gz"
        mock_sitk.N4BiasFieldCorrectionImageFilter.return_value.Execute.assert_called_once()

    async def test_raises_without_sitk(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"SimpleITK": None}):
            with self.assertRaisesRegex(ImportError, "pirn-health\\[mri\\]"):
                await knot.process(nifti_path="in.nii.gz", output_nifti_path="out.nii.gz")
