"""Unit tests for :class:`MRIQualityController`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.mri_quality_controller import MRIQualityController
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_modality(self) -> None:
        with self.assertRaisesRegex(ValueError, "modality"):
            MRIQualityController(
                mri_data=Parameter("md", dict, default={}, _config=KnotConfig(id="md")),
                snr_threshold=10.0,
                motion_threshold_mm=0.5,
                modality="CT",
                _config=KnotConfig(id="q"),
            )

    def test_rejects_non_positive_snr_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "snr_threshold"):
            MRIQualityController(
                mri_data=Parameter("md", dict, default={}, _config=KnotConfig(id="md")),
                snr_threshold=0.0,
                motion_threshold_mm=0.5,
                modality="T1w",
                _config=KnotConfig(id="q"),
            )

    def test_rejects_non_positive_motion_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "motion_threshold_mm"):
            MRIQualityController(
                mri_data=Parameter("md", dict, default={}, _config=KnotConfig(id="md")),
                snr_threshold=10.0,
                motion_threshold_mm=0.0,
                modality="T1w",
                _config=KnotConfig(id="q"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        mri = {"nifti_path": "scan.nii.gz", "motion_params": [0.1, 0.2]}
        with Tapestry() as t:
            MRIQualityController(
                mri_data=Parameter("md", dict, default=mri, _config=KnotConfig(id="md")),
                snr_threshold=10.0,
                motion_threshold_mm=0.5,
                modality="T1w",
                _config=KnotConfig(id="q"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["q"]
        assert isinstance(out, dict)
        assert "snr" in out
        assert "passes_qc" in out
        assert "qc_flags" in out

    async def test_no_motion_params(self) -> None:
        mri = {"nifti_path": "scan.nii.gz", "motion_params": None}
        with Tapestry() as t:
            MRIQualityController(
                mri_data=Parameter("md", dict, default=mri, _config=KnotConfig(id="md")),
                snr_threshold=10.0,
                motion_threshold_mm=0.5,
                modality="T1w",
                _config=KnotConfig(id="q"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["q"]
        assert out["mean_fd_mm"] is None
