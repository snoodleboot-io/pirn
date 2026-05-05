"""Unit tests for :class:`BiasFieldCorrector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.bias_field_corrector import BiasFieldCorrector
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            BiasFieldCorrector(
                nifti_path="",
                output_nifti_path="out",
                _config=KnotConfig(id="b"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_corrected_path(self) -> None:
        with Tapestry() as t:
            BiasFieldCorrector(
                nifti_path="in.nii.gz",
                output_nifti_path="out.nii.gz",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["b"] == "out.nii.gz"
