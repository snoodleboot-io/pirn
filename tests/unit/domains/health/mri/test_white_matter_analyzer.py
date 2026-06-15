"""Unit tests for :class:`WhiteMatterAnalyzer`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.white_matter_analyzer import WhiteMatterAnalyzer

_CFG = KnotConfig(id="w")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> WhiteMatterAnalyzer:
        return WhiteMatterAnalyzer(dwi_nifti_path="x.nii", bvec_path="b", bval_path="v", tracts=["cc"], _config=_CFG)

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(dwi_nifti_path="", bvec_path="b", bval_path="v", tracts=[])

    async def test_rejects_non_sequence_tracts(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "tracts"):
            await knot.process(dwi_nifti_path="x", bvec_path="b", bval_path="v", tracts=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_tract(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(dwi_nifti_path="x", bvec_path="b", bval_path="v", tracts=[1])  # type: ignore[list-item]

    async def test_returns_per_tract_mapping(self) -> None:
        knot = self._make_knot()
        mock_nib = MagicMock()
        mock_img = MagicMock()
        mock_img.dataobj = [[[1.0]]]
        mock_img.affine = None
        mock_nib.load.return_value = mock_img
        mock_gtab = MagicMock()
        mock_gradient_table = MagicMock(return_value=mock_gtab)
        mock_fit = MagicMock()
        mock_fit.fa = [[[0.5]]]
        mock_fit.md = [[[0.001]]]
        mock_model_instance = MagicMock()
        mock_model_instance.fit.return_value = mock_fit
        mock_tensor_model = MagicMock(return_value=mock_model_instance)
        with patch("pirn.domains.health.mri.white_matter_analyzer.nib", mock_nib), \
             patch("pirn.domains.health.mri.white_matter_analyzer.gradient_table", mock_gradient_table), \
             patch("pirn.domains.health.mri.white_matter_analyzer.TensorModel", mock_tensor_model), \
             patch("pirn.domains.health.mri.white_matter_analyzer._HAS_DIPY", True), \
             patch("numpy.loadtxt", return_value=MagicMock()):
            out = await knot.process(
                dwi_nifti_path="dwi.nii.gz",
                bvec_path="bvecs",
                bval_path="bvals",
                tracts=["CST", "CC"],
            )
        assert isinstance(out, dict)
        assert "CST" in out
        assert "fa" in out["CST"]
        assert "md" in out["CST"]
