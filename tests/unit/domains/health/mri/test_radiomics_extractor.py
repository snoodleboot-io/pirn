"""Unit tests for :class:`RadiomicsExtractor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.radiomics_extractor import RadiomicsExtractor

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RadiomicsExtractor:
        return RadiomicsExtractor(image_path="i.nii.gz", mask_path="m.nii.gz", feature_classes=["firstorder"], _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(image_path="", mask_path="m", feature_classes=[])

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "feature_classes"):
            await knot.process(image_path="i", mask_path="m", feature_classes=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_class(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(image_path="i", mask_path="m", feature_classes=[1])  # type: ignore[list-item]

    async def test_returns_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(image_path="i.nii.gz", mask_path="m.nii.gz", feature_classes=["firstorder"])
        assert isinstance(out, Mapping)
