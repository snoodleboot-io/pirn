"""Unit tests for :class:`VolumetricAnalyzer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig

from pirn_health.mri.volumetric_analyzer import VolumetricAnalyzer

_CFG = KnotConfig(id="v")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VolumetricAnalyzer:
        return VolumetricAnalyzer(labelled_nifti_path="x", regions=["frontal"], _config=_CFG)

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(labelled_nifti_path="", regions=[])

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "regions"):
            await knot.process(labelled_nifti_path="x", regions=42)

    async def test_rejects_non_string_region(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(labelled_nifti_path="x", regions=[1])

    async def test_raises_not_implemented_for_valid_input(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(NotImplementedError, "nibabel"):
            await knot.process(labelled_nifti_path="x", regions=["frontal"])
