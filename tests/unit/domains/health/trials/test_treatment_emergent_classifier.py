"""Unit tests for :class:`TreatmentEmergentClassifier`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.treatment_emergent_classifier import (
    TreatmentEmergentClassifier,
)
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry


@knot
async def emit_events() -> Sequence[ClinicalTrialRecord]:
    return (
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-1",
            visit_number=1,
            observation_codes=("AE001",),
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-1",
            visit_number=2,
            observation_codes=("AE002",),
            observed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        ),
    )


@knot
async def emit_exposures() -> Mapping[str, datetime]:
    return {"S-1": datetime(2026, 4, 15, tzinfo=timezone.utc)}


class TestConstruction:
    def test_rejects_non_knot_events(self) -> None:
        with Tapestry():
            exposures = emit_exposures(_config=KnotConfig(id="e"))
            with pytest.raises(TypeError, match="events"):
                TreatmentEmergentClassifier(
                    events="not-a-knot",  # type: ignore[arg-type]
                    exposures=exposures,
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_non_knot_exposures(self) -> None:
        with Tapestry():
            events = emit_events(_config=KnotConfig(id="ev"))
            with pytest.raises(TypeError, match="exposures"):
                TreatmentEmergentClassifier(
                    events=events,
                    exposures="not-a-knot",  # type: ignore[arg-type]
                    _config=KnotConfig(id="c"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_flags_only_post_exposure_events(self) -> None:
        with Tapestry() as t:
            events = emit_events(_config=KnotConfig(id="ev"))
            exposures = emit_exposures(_config=KnotConfig(id="ex"))
            TreatmentEmergentClassifier(
                events=events,
                exposures=exposures,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert len(out) == 2
        # First event (April 1) is before April 15 exposure -> not emergent.
        # Second event (May 1) is after exposure -> emergent.
        assert out[0]["treatment_emergent"] is False
        assert out[1]["treatment_emergent"] is True
        assert out[1]["subject_id"] == "S-1"
        assert "T" in out[0]["observed_at"]  # ISO timestamp string
