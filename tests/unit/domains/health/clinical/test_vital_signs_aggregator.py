"""Unit tests for :class:`VitalSignsAggregator`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.vital_signs_aggregator import (
    VitalSignsAggregator,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="rows"):
            VitalSignsAggregator(
                rows=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="a"),
            )

    def test_rejects_non_mapping_row(self) -> None:
        with pytest.raises(TypeError, match="row"):
            VitalSignsAggregator(
                rows=["x"],  # type: ignore[list-item]
                _config=KnotConfig(id="a"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_aggregates_per_patient(self) -> None:
        rows = (
            {"patient_id": "P1", "vital_name": "hr", "value": 70.0},
            {"patient_id": "P1", "vital_name": "hr", "value": 80.0},
        )
        with Tapestry() as t:
            VitalSignsAggregator(
                rows=rows,
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, Mapping)
        assert "P1" in out
        assert "hr" in out["P1"]
        assert out["P1"]["hr"]["max"] == 80.0
        assert out["P1"]["hr"]["min"] == 70.0
