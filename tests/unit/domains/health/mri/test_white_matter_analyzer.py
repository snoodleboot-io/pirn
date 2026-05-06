"""Unit tests for :class:`WhiteMatterAnalyzer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

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
        out = await knot.process(dwi_nifti_path="x.nii", bvec_path="b", bval_path="v", tracts=["cc"])
        assert isinstance(out, Mapping)
        assert "cc" in out
        assert "fa" in out["cc"]
