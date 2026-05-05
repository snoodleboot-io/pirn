"""Unit tests for :class:`IntensityNormalizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.intensity_normalizer import IntensityNormalizer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            IntensityNormalizer(
                nifti_path="",
                method="zscore",
                output_nifti_path="out",
                _config=KnotConfig(id="n"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            IntensityNormalizer(
                nifti_path="x",
                method="bogus",
                output_nifti_path="out",
                _config=KnotConfig(id="n"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_normalised_path(self) -> None:
        with Tapestry() as t:
            IntensityNormalizer(
                nifti_path="in.nii.gz",
                method="zscore",
                output_nifti_path="norm.nii.gz",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["n"] == "norm.nii.gz"
