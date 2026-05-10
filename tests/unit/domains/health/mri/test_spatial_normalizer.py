"""Unit tests for :class:`SpatialNormalizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.mri.spatial_normalizer import SpatialNormalizer
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="s")
_IMAGE = {"nifti_path": "t1.nii.gz", "voxel_size_mm": [1.0, 1.0, 1.0]}


def _make_knot() -> SpatialNormalizer:
    with Tapestry():
        src = Parameter("img", dict, default=_IMAGE, _config=KnotConfig(id="img"))
        return SpatialNormalizer(image=src, template="MNI152", registration_type="linear", degrees_of_freedom=12, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_template(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "template"):
            await knot.process(image=_IMAGE, template="MNI305", registration_type="linear", degrees_of_freedom=12)

    async def test_rejects_invalid_registration_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "registration_type"):
            await knot.process(image=_IMAGE, template="MNI152", registration_type="affine", degrees_of_freedom=12)

    async def test_rejects_invalid_dof(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "degrees_of_freedom"):
            await knot.process(image=_IMAGE, template="MNI152", registration_type="linear", degrees_of_freedom=3)

    async def test_returns_dict(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        knot = _make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(image=_IMAGE, template="MNI152", registration_type="linear", degrees_of_freedom=12)
        assert isinstance(out, dict)
        assert out["template"] == "MNI152"
        assert "warped_image_path" in out
        assert "warp_field_path" in out
