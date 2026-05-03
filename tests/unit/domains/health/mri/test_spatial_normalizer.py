"""Unit tests for :class:`SpatialNormalizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.spatial_normalizer import SpatialNormalizer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_invalid_template(self) -> None:
        with pytest.raises(ValueError, match="template"):
            SpatialNormalizer(
                image=Parameter("img", dict, default={}, _config=KnotConfig(id="img")),
                template="MNI305",
                registration_type="linear",
                degrees_of_freedom=12,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_invalid_registration_type(self) -> None:
        with pytest.raises(ValueError, match="registration_type"):
            SpatialNormalizer(
                image=Parameter("img", dict, default={}, _config=KnotConfig(id="img")),
                template="MNI152",
                registration_type="affine",
                degrees_of_freedom=12,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_invalid_dof(self) -> None:
        with pytest.raises(ValueError, match="degrees_of_freedom"):
            SpatialNormalizer(
                image=Parameter("img", dict, default={}, _config=KnotConfig(id="img")),
                template="MNI152",
                registration_type="linear",
                degrees_of_freedom=3,
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        image_data = {"nifti_path": "t1.nii.gz", "voxel_size_mm": [1.0, 1.0, 1.0]}
        with Tapestry() as t:
            SpatialNormalizer(
                image=Parameter("img", dict, default=image_data, _config=KnotConfig(id="img")),
                template="MNI152",
                registration_type="linear",
                degrees_of_freedom=12,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, dict)
        assert out["template"] == "MNI152"
        assert "warped_image_path" in out
        assert "warp_field_path" in out
