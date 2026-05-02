"""Unit tests for :class:`LabResultNormalizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.lab_result_normalizer import (
    LabResultNormalizer,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_rows(self) -> None:
        with pytest.raises(TypeError, match="rows"):
            LabResultNormalizer(
                rows=42,  # type: ignore[arg-type]
                unit_conversions={},
                target_unit="mg/dL",
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_mapping_conversions(self) -> None:
        with pytest.raises(TypeError, match="unit_conversions"):
            LabResultNormalizer(
                rows=[],
                unit_conversions=42,  # type: ignore[arg-type]
                target_unit="mg/dL",
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_string_target_unit(self) -> None:
        with pytest.raises(TypeError, match="target_unit"):
            LabResultNormalizer(
                rows=[],
                unit_conversions={},
                target_unit=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="n"),
            )

    def test_rejects_empty_target_unit(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            LabResultNormalizer(
                rows=[],
                unit_conversions={},
                target_unit="",
                _config=KnotConfig(id="n"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_tuple(self) -> None:
        with Tapestry() as t:
            LabResultNormalizer(
                rows=[{"value": 100.0, "unit": "mg/dL"}],
                unit_conversions={("mg/dL", "mmol/L"): 0.0555},
                target_unit="mmol/L",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["unit"] == "mmol/L"
