"""Unit tests for :class:`RegionOfInterestExtractor`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.region_of_interest_extractor import (
    RegionOfInterestExtractor,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            RegionOfInterestExtractor(
                nifti_path="",
                atlas_label_path="a",
                roi_labels=[],
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="roi_labels"):
            RegionOfInterestExtractor(
                nifti_path="x",
                atlas_label_path="a",
                roi_labels=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_int_label(self) -> None:
        with pytest.raises(TypeError, match="int"):
            RegionOfInterestExtractor(
                nifti_path="x",
                atlas_label_path="a",
                roi_labels=["x"],  # type: ignore[list-item]
                _config=KnotConfig(id="r"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_mapping(self) -> None:
        with Tapestry() as t:
            RegionOfInterestExtractor(
                nifti_path="x.nii",
                atlas_label_path="a.nii",
                roi_labels=[1, 2],
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {1, 2}
