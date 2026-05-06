"""Unit tests for :class:`EstimandAlignedAnalyzer`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.trials.estimand_aligned_analyzer import EstimandAlignedAnalyzer
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry

_RECORDS = (
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
        observation_codes=("DISCONT",),
        observed_at=datetime(2026, 4, 5, tzinfo=UTC),
    ),
)


def _make_knot(strategy: str = "treatment-policy") -> EstimandAlignedAnalyzer:
    with Tapestry():
        from pirn.core.parameter import Parameter
        src = Parameter("rec", tuple, default=_RECORDS, _config=KnotConfig(id="rec"))
        return EstimandAlignedAnalyzer(
            records=src,
            strategy=strategy,
            _config=KnotConfig(id="e"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_strategy(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "strategy"):
            await knot.process(
                records=_RECORDS,
                strategy="not-a-real-strategy",
            )

    async def test_rejects_non_string_strategy(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "strategy"):
            await knot.process(
                records=_RECORDS,
                strategy=42,  # type: ignore[arg-type]
            )

    async def test_rejects_non_sequence_intercurrent_codes(self) -> None:
        knot = _make_knot(strategy="while-on-treatment")
        with self.assertRaisesRegex(TypeError, "intercurrent_event_codes"):
            await knot.process(
                records=_RECORDS,
                strategy="while-on-treatment",
                intercurrent_event_codes=42,  # type: ignore[arg-type]
            )

    async def test_treatment_policy_returns_input_unchanged(self) -> None:
        knot = _make_knot()
        out = await knot.process(
            records=_RECORDS,
            strategy="treatment-policy",
            intercurrent_event_codes=("DISCONT",),
        )
        assert len(out) == 2

    async def test_while_on_treatment_excludes_intercurrent(self) -> None:
        knot = _make_knot(strategy="while-on-treatment")
        out = await knot.process(
            records=_RECORDS,
            strategy="while-on-treatment",
            intercurrent_event_codes=("DISCONT",),
        )
        assert len(out) == 1
        assert out[0].observation_codes == ("AE001",)

    async def test_hypothetical_filters_intercurrent(self) -> None:
        knot = _make_knot(strategy="hypothetical")
        out = await knot.process(
            records=_RECORDS,
            strategy="hypothetical",
            intercurrent_event_codes=("DISCONT",),
        )
        assert len(out) == 1

    async def test_principal_stratum_returns_input_unchanged(self) -> None:
        knot = _make_knot(strategy="principal-stratum")
        out = await knot.process(
            records=_RECORDS,
            strategy="principal-stratum",
        )
        assert len(out) == 2

    async def test_composite_strategy_returns_input_unchanged(self) -> None:
        knot = _make_knot(strategy="composite-strategy")
        out = await knot.process(
            records=_RECORDS,
            strategy="composite-strategy",
        )
        assert len(out) == 2
