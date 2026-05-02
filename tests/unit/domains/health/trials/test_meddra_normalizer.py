"""Unit tests for :class:`MedDRANormalizer`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.meddra_normalizer import MedDRANormalizer
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry


@knot
async def emit_records() -> Sequence[ClinicalTrialRecord]:
    return (
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-1",
            visit_number=1,
            observation_codes=("headache",),
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-2",
            visit_number=1,
            observation_codes=("unknown-term",),
            observed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        ),
    )


class TestConstruction:
    def test_rejects_non_knot_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            MedDRANormalizer(
                records="not-a-knot",  # type: ignore[arg-type]
                term_to_pt={"headache": "Headache"},
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_mapping_term_to_pt(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(TypeError, match="term_to_pt"):
                MedDRANormalizer(
                    records=r,
                    term_to_pt=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="n"),
                )

    def test_rejects_empty_term_to_pt(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="term_to_pt"):
                MedDRANormalizer(
                    records=r,
                    term_to_pt={},
                    _config=KnotConfig(id="n"),
                )

    def test_rejects_blank_term_to_pt_value(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="term_to_pt values"):
                MedDRANormalizer(
                    records=r,
                    term_to_pt={"headache": ""},
                    _config=KnotConfig(id="n"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_maps_known_terms_and_falls_back_for_unknown(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            MedDRANormalizer(
                records=r,
                term_to_pt={"headache": "Headache"},
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert out[0]["meddra_pt"] == "Headache"
        assert out[1]["meddra_pt"] == "unknown-term"
        assert out[0]["subject_id"] == "S-1"
        assert out[1]["subject_id"] == "S-2"
