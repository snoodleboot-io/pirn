"""Unit tests for :class:`VBMMorphometryAnalyzer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.mri.vbm_morphometry_analyzer import VBMMorphometryAnalyzer
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="v")
_IMAGE = {"nifti_path": "normalized.nii.gz", "voxel_size_mm": [1.5, 1.5, 1.5], "n_voxels": 100000}


def _make_knot() -> VBMMorphometryAnalyzer:
    with Tapestry():
        src = Parameter("ni", dict, default=_IMAGE, _config=KnotConfig(id="ni"))
        return VBMMorphometryAnalyzer(normalized_image=src, tissue_type="gray_matter", smoothing_fwhm_mm=8.0, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_tissue_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "tissue_type"):
            await knot.process(normalized_image=_IMAGE, tissue_type="myelin", smoothing_fwhm_mm=8.0)

    async def test_rejects_non_positive_smoothing(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "smoothing_fwhm_mm"):
            await knot.process(normalized_image=_IMAGE, tissue_type="gray_matter", smoothing_fwhm_mm=0.0)

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(normalized_image=_IMAGE, tissue_type="gray_matter", smoothing_fwhm_mm=8.0)
        assert isinstance(out, dict)
        assert out["tissue_type"] == "gray_matter"
        assert "tissue_volume_ml" in out
        assert "smoothed_map_path" in out
