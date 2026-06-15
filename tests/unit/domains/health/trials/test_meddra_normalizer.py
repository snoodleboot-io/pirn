"""Unit tests for :class:`MedDRANormalizer`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_health.trials.meddra_normalizer import MedDRANormalizer
from pirn_health.types.clinical_trial_record import ClinicalTrialRecord

_RECORDS = (
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=1,
        observation_codes=("headache",),
        observed_at=datetime(2026, 4, 1, tzinfo=UTC),
    ),
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-2",
        visit_number=1,
        observation_codes=("unknown-term",),
        observed_at=datetime(2026, 4, 2, tzinfo=UTC),
    ),
)
_TERM_TO_PT = {"headache": "Headache"}


def _make_knot() -> MedDRANormalizer:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("rec", tuple, default=_RECORDS, _config=KnotConfig(id="rec"))
        return MedDRANormalizer(
            records=src,
            term_to_pt=_TERM_TO_PT,
            _config=KnotConfig(id="n"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_term_to_pt(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "term_to_pt"):
            await knot.process(records=_RECORDS, term_to_pt={})

    async def test_rejects_blank_term_to_pt_value(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "term_to_pt values"):
            await knot.process(records=_RECORDS, term_to_pt={"headache": ""})

    async def test_maps_known_terms_and_falls_back_for_unknown(self) -> None:
        knot = _make_knot()
        out = await knot.process(records=_RECORDS, term_to_pt=_TERM_TO_PT)
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert out[0]["meddra_pt"] == "Headache"
        assert out[1]["meddra_pt"] == "unknown-term"
        assert out[0]["subject_id"] == "S-1"
        assert out[1]["subject_id"] == "S-2"
