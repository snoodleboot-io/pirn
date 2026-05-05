"""Unit tests for :class:`NIfTIConverter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.nifti_converter import NIfTIConverter
from pirn.domains.health.types.dicom_series import DICOMSeries
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_series(self) -> None:
        with self.assertRaisesRegex(TypeError, "DICOMSeries"):
            NIfTIConverter(
                series="x",  # type: ignore[arg-type]
                output_nifti_path="out",
                _config=KnotConfig(id="c"),
            )

    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            NIfTIConverter(
                series=DICOMSeries(),
                output_nifti_path="",
                _config=KnotConfig(id="c"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_nifti_path(self) -> None:
        with Tapestry() as t:
            NIfTIConverter(
                series=DICOMSeries(),
                output_nifti_path="out.nii.gz",
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["c"] == "out.nii.gz"
