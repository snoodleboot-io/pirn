"""Unit tests for :class:`ImageRegistrar`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.image_registrar import ImageRegistrar
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ImageRegistrar(
                moving_path="",
                fixed_path="f",
                transform="rigid",
                output_registered_path="out",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_invalid_transform(self) -> None:
        with self.assertRaisesRegex(ValueError, "transform"):
            ImageRegistrar(
                moving_path="m",
                fixed_path="f",
                transform="bogus",
                output_registered_path="out",
                _config=KnotConfig(id="r"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_registered_path(self) -> None:
        with Tapestry() as t:
            ImageRegistrar(
                moving_path="m.nii.gz",
                fixed_path="f.nii.gz",
                transform="affine",
                output_registered_path="reg.nii.gz",
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["r"] == "reg.nii.gz"
