"""Unit tests for :class:`RegionOfInterestExtractor`."""

from __future__ import annotations

import unittest

try:
    import nibabel  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("nibabel not installed") from _e

from collections.abc import Mapping
from unittest.mock import MagicMock, patch

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.region_of_interest_extractor import RegionOfInterestExtractor

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RegionOfInterestExtractor:
        return RegionOfInterestExtractor(
            nifti_path="x.nii", atlas_label_path="a.nii", roi_labels=[1, 2], _config=_CFG
        )

    def _mock_nib(self) -> MagicMock:
        intensity = np.array([[[1.0, 2.0], [3.0, 4.0]]])
        labels = np.array([[[1, 2], [1, 2]]])
        mock_img = MagicMock()
        mock_img.get_fdata.return_value = intensity
        mock_atlas = MagicMock()
        mock_atlas.get_fdata.return_value = labels
        mock_nib = MagicMock()
        mock_nib.load.side_effect = [mock_img, mock_atlas]
        return mock_nib

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
        with patch("pirn.domains.health.mri.region_of_interest_extractor.nib", self._mock_nib()):
            out = await knot.process(nifti_path="x.nii", atlas_label_path="a.nii", roi_labels=[1, 2])
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {1, 2}
