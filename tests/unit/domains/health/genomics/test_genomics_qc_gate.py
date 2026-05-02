"""Unit tests for :class:`GenomicsQCGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.genomics_qc_gate import (
    GenomicsQCError,
    GenomicsQCGate,
)
from pirn.domains.health.types.genomics_record import GenomicsRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="records"):
            GenomicsQCGate(
                records=42,  # type: ignore[arg-type]
                min_quality=10.0,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_record(self) -> None:
        with pytest.raises(TypeError, match="GenomicsRecord"):
            GenomicsQCGate(
                records=["x"],  # type: ignore[list-item]
                min_quality=10.0,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            GenomicsQCGate(
                records=(),
                min_quality="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="g"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_passes_when_quality_above(self) -> None:
        records = (GenomicsRecord(sample_id="S1", quality_score=20.0),)
        with Tapestry() as t:
            GenomicsQCGate(
                records=records,
                min_quality=10.0,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert isinstance(out, tuple)
        assert len(out) == 1

    async def test_fails_when_quality_below(self) -> None:
        records = (GenomicsRecord(sample_id="S1", quality_score=5.0),)
        with Tapestry() as t:
            GenomicsQCGate(
                records=records,
                min_quality=10.0,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert any(
            rec.exc_type == GenomicsQCError.__name__
            for rec in result.exceptions
        )
