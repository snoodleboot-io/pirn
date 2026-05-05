"""Unit tests for :class:`VolumetricAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.volumetric_analyzer import VolumetricAnalyzer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            VolumetricAnalyzer(
                labelled_nifti_path="",
                regions=[],
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "regions"):
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="v"),
            )

    def test_rejects_non_string_region(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="v"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_region_mapping(self) -> None:
        with Tapestry() as t:
            VolumetricAnalyzer(
                labelled_nifti_path="x",
                regions=["frontal"],
                _config=KnotConfig(id="v"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["v"]
        assert isinstance(out, Mapping)
        assert "frontal" in out
