"""Unit tests for :class:`VBMMorphometryAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.vbm_morphometry_analyzer import VBMMorphometryAnalyzer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_tissue_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "tissue_type"):
            VBMMorphometryAnalyzer(
                normalized_image=Parameter("ni", dict, default={}, _config=KnotConfig(id="ni")),
                tissue_type="myelin",
                smoothing_fwhm_mm=8.0,
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_positive_smoothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "smoothing_fwhm_mm"):
            VBMMorphometryAnalyzer(
                normalized_image=Parameter("ni", dict, default={}, _config=KnotConfig(id="ni")),
                tissue_type="gray_matter",
                smoothing_fwhm_mm=0.0,
                _config=KnotConfig(id="v"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        image_data = {
            "nifti_path": "normalized.nii.gz",
            "voxel_size_mm": [1.5, 1.5, 1.5],
            "n_voxels": 100000,
        }
        with Tapestry() as t:
            VBMMorphometryAnalyzer(
                normalized_image=Parameter("ni", dict, default=image_data, _config=KnotConfig(id="ni")),
                tissue_type="gray_matter",
                smoothing_fwhm_mm=8.0,
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert isinstance(out, dict)
        assert out["tissue_type"] == "gray_matter"
        assert "tissue_volume_ml" in out
        assert "smoothed_map_path" in out
