"""Unit tests for :class:`ClinicalEventAggregator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.trials.clinical_event_aggregator import ClinicalEventAggregator
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="a")
_RECORDS: tuple[ClinicalTrialRecord, ...] = (
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=1,
        observation_codes=("AE001", "AE002"),
        observed_at=datetime(2026, 4, 1, tzinfo=UTC),
    ),
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=2,
        observation_codes=("AE001",),
        observed_at=datetime(2026, 4, 2, tzinfo=UTC),
    ),
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-2",
        visit_number=1,
        observation_codes=("AE002",),
        observed_at=datetime(2026, 4, 1, tzinfo=UTC),
    ),
)


def _make_knot() -> ClinicalEventAggregator:
    with Tapestry():
        src = Parameter("rec", tuple, default=_RECORDS, _config=KnotConfig(id="rec"))
        return ClinicalEventAggregator(records=src, event_codes=("AE001", "AE002"), _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_event_codes(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "event_codes"):
            await knot.process(records=_RECORDS, event_codes=42)  # type: ignore[arg-type]

    async def test_rejects_empty_event_codes(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "event_codes"):
            await knot.process(records=_RECORDS, event_codes=())

    async def test_rejects_blank_event_code(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "event_code"):
            await knot.process(records=_RECORDS, event_codes=("",))

    async def test_aggregates_per_subject_per_event(self) -> None:
        knot = _make_knot()
        out = await knot.process(records=_RECORDS, event_codes=("AE001", "AE002"))
        assert isinstance(out, Mapping)
        assert out["S-1"]["AE001"] == 2
        assert out["S-1"]["AE002"] == 1
        assert out["S-2"]["AE001"] == 0
        assert out["S-2"]["AE002"] == 1
