"""Unit tests for :class:`BiasFieldCorrector`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.bias_field_corrector import BiasFieldCorrector

_CFG = KnotConfig(id="b")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BiasFieldCorrector:
        return BiasFieldCorrector(nifti_path="in.nii.gz", output_nifti_path="out.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", output_nifti_path="out.nii.gz")

    async def test_returns_corrected_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="in.nii.gz", output_nifti_path="out.nii.gz")
        assert out == "out.nii.gz"
