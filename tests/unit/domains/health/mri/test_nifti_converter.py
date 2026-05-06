"""Unit tests for :class:`NIfTIConverter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.nifti_converter import NIfTIConverter
from pirn.domains.health.types.dicom_series import DICOMSeries

_CFG = KnotConfig(id="c")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> NIfTIConverter:
        return NIfTIConverter(series=DICOMSeries(), output_nifti_path="out.nii.gz", _config=_CFG)

    async def test_rejects_non_series(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DICOMSeries"):
            await knot.process(series="x", output_nifti_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(series=DICOMSeries(), output_nifti_path="")

    async def test_returns_nifti_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(series=DICOMSeries(), output_nifti_path="out.nii.gz")
        assert out == "out.nii.gz"
