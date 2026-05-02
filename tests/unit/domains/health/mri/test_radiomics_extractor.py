"""Unit tests for :class:`RadiomicsExtractor`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.radiomics_extractor import RadiomicsExtractor
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            RadiomicsExtractor(
                image_path="",
                mask_path="m",
                feature_classes=[],
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="feature_classes"):
            RadiomicsExtractor(
                image_path="i",
                mask_path="m",
                feature_classes=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_string_class(self) -> None:
        with pytest.raises(TypeError, match="string"):
            RadiomicsExtractor(
                image_path="i",
                mask_path="m",
                feature_classes=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="r"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_mapping(self) -> None:
        with Tapestry() as t:
            RadiomicsExtractor(
                image_path="i.nii.gz",
                mask_path="m.nii.gz",
                feature_classes=["firstorder"],
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, Mapping)
