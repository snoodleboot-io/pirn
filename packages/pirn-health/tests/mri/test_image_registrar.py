"""Unit tests for :class:`ImageRegistrar`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_health.mri.image_registrar import ImageRegistrar

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ImageRegistrar:
        return ImageRegistrar(
            moving_path="m.nii.gz",
            fixed_path="f.nii.gz",
            transform="affine",
            output_registered_path="reg.nii.gz",
            _config=_CFG,
        )

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(
                moving_path="", fixed_path="f", transform="rigid", output_registered_path="out"
            )

    async def test_rejects_invalid_transform(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "transform"):
            await knot.process(
                moving_path="m", fixed_path="f", transform="bogus", output_registered_path="out"
            )

    async def test_returns_registered_path(self) -> None:
        knot = self._make_knot()
        mock_sitk = MagicMock()
        mock_img = MagicMock()
        mock_sitk.ReadImage.return_value = mock_img
        mock_sitk.sitkFloat32 = 0
        mock_sitk.sitkLinear = 1
        mock_sitk.ImageRegistrationMethod.return_value = MagicMock()
        mock_sitk.Resample.return_value = mock_img

        with patch.object(
            OptionalDependency,
            "require",
            side_effect=lambda module, **_: {"SimpleITK": mock_sitk}[module],
        ):
            out = await knot.process(
                moving_path="m.nii.gz",
                fixed_path="f.nii.gz",
                transform="affine",
                output_registered_path="reg.nii.gz",
            )
        assert out == "reg.nii.gz"

    async def test_raises_without_sitk(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"SimpleITK": None}):
            with self.assertRaisesRegex(ImportError, "pirn-health\\[mri\\]"):
                await knot.process(
                    moving_path="m.nii.gz",
                    fixed_path="f.nii.gz",
                    transform="affine",
                    output_registered_path="reg.nii.gz",
                )
