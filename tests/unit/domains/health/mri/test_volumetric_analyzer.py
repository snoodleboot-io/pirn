"""Unit tests for :class:`VolumetricAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.volumetric_analyzer import VolumetricAnalyzer

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
            await knot.process(labelled_nifti_path="x", regions=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_region(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(labelled_nifti_path="x", regions=[1])  # type: ignore[list-item]

    async def test_returns_per_region_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(labelled_nifti_path="x", regions=["frontal"])
        assert isinstance(out, Mapping)
        assert "frontal" in out
