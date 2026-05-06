"""Unit tests for :class:`RegionOfInterestExtractor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.region_of_interest_extractor import RegionOfInterestExtractor

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RegionOfInterestExtractor:
        return RegionOfInterestExtractor(nifti_path="x.nii", atlas_label_path="a.nii", roi_labels=[1, 2], _config=_CFG)

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(nifti_path="", atlas_label_path="a", roi_labels=[])

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "roi_labels"):
            await knot.process(nifti_path="x", atlas_label_path="a", roi_labels=42)  # type: ignore[arg-type]

    async def test_rejects_non_int_label(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "int"):
            await knot.process(nifti_path="x", atlas_label_path="a", roi_labels=["x"])  # type: ignore[list-item]

    async def test_returns_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(nifti_path="x.nii", atlas_label_path="a.nii", roi_labels=[1, 2])
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {1, 2}
