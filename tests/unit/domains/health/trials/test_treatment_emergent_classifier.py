"""Unit tests for :class:`TreatmentEmergentClassifier`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.treatment_emergent_classifier import (
    TreatmentEmergentClassifier,
)
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry

_EVENTS = (
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=1,
        observation_codes=("AE001",),
        observed_at=datetime(2026, 4, 1, tzinfo=UTC),
    ),
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=2,
        observation_codes=("AE002",),
        observed_at=datetime(2026, 5, 1, tzinfo=UTC),
    ),
)
_EXPOSURES = {"S-1": datetime(2026, 4, 15, tzinfo=UTC)}


def _make_knot() -> TreatmentEmergentClassifier:
    with Tapestry():
        from pirn.core.parameter import Parameter
        ev = Parameter("ev", tuple, default=_EVENTS, _config=KnotConfig(id="ev"))
        ex = Parameter("ex", dict, default=_EXPOSURES, _config=KnotConfig(id="ex"))
        return TreatmentEmergentClassifier(
            events=ev,
            exposures=ex,
            _config=KnotConfig(id="c"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_flags_only_post_exposure_events(self) -> None:
        knot = _make_knot()
        out = await knot.process(events=_EVENTS, exposures=_EXPOSURES)
        assert len(out) == 2
        # First event (April 1) is before April 15 exposure -> not emergent.
        # Second event (May 1) is after exposure -> emergent.
        assert out[0]["treatment_emergent"] is False
        assert out[1]["treatment_emergent"] is True
        assert out[1]["subject_id"] == "S-1"
        assert "T" in out[0]["observed_at"]  # ISO timestamp string
