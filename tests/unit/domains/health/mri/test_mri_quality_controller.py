"""Unit tests for :class:`MRIQualityController`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.mri.mri_quality_controller import MRIQualityController
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="q")
_MRI = {"nifti_path": "scan.nii.gz", "motion_params": [0.1, 0.2]}


def _make_knot() -> MRIQualityController:
    with Tapestry():
        src = Parameter("md", dict, default=_MRI, _config=KnotConfig(id="md"))
        return MRIQualityController(mri_data=src, snr_threshold=10.0, motion_threshold_mm=0.5, modality="T1w", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_modality(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "modality"):
            await knot.process(mri_data=_MRI, snr_threshold=10.0, motion_threshold_mm=0.5, modality="CT")

    async def test_rejects_non_positive_snr_threshold(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "snr_threshold"):
            await knot.process(mri_data=_MRI, snr_threshold=0.0, motion_threshold_mm=0.5, modality="T1w")

    async def test_rejects_non_positive_motion_threshold(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "motion_threshold_mm"):
            await knot.process(mri_data=_MRI, snr_threshold=10.0, motion_threshold_mm=0.0, modality="T1w")

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(mri_data=_MRI, snr_threshold=10.0, motion_threshold_mm=0.5, modality="T1w")
        assert isinstance(out, dict)
        assert "snr" in out
        assert "passes_qc" in out
        assert "qc_flags" in out

    async def test_no_motion_params(self) -> None:
        knot = _make_knot()
        mri = {"nifti_path": "scan.nii.gz", "motion_params": None}
        out = await knot.process(mri_data=mri, snr_threshold=10.0, motion_threshold_mm=0.5, modality="T1w")
        assert out["mean_fd_mm"] is None
