"""Unit tests for :class:`ImageRegistrar`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.image_registrar import ImageRegistrar

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ImageRegistrar:
        return ImageRegistrar(moving_path="m.nii.gz", fixed_path="f.nii.gz", transform="affine", output_registered_path="reg.nii.gz", _config=_CFG)

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(moving_path="", fixed_path="f", transform="rigid", output_registered_path="out")

    async def test_rejects_invalid_transform(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "transform"):
            await knot.process(moving_path="m", fixed_path="f", transform="bogus", output_registered_path="out")

    async def test_returns_registered_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(moving_path="m.nii.gz", fixed_path="f.nii.gz", transform="affine", output_registered_path="reg.nii.gz")
        assert out == "reg.nii.gz"
