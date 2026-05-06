"""Unit tests for :class:`DeviationSurvey`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.oilgas.types.deviation_survey import DeviationSurvey


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        survey = DeviationSurvey()
        assert survey.well_id == ""
        assert survey.station_count == 0
        assert isinstance(survey.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        survey = DeviationSurvey(well_id="W1", station_count=10, fetched_at=when)
        assert survey.well_id == "W1"
        assert survey.station_count == 10
        assert survey.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_keys(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        survey = DeviationSurvey(well_id="W1", station_count=3, fetched_at=when)
        d = survey._pirn_audit_dict()
        assert d == {
            "well_id": "W1",
            "station_count": 3,
            "fetched_at": when.isoformat(),
        }


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        survey = DeviationSurvey(well_id="W1")
        try:
            survey.station_count = 5  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DeviationSurvey must be frozen")
