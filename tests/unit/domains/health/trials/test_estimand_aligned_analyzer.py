"""Unit tests for :class:`EstimandAlignedAnalyzer`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.estimand_aligned_analyzer import (
    EstimandAlignedAnalyzer,
)
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry


@knot
async def emit_records() -> Sequence[ClinicalTrialRecord]:
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
            observation_codes=("DISCONT",),
            observed_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        ),
    )


class TestConstruction:
    def test_rejects_non_knot_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            EstimandAlignedAnalyzer(
                records="not-a-knot",  # type: ignore[arg-type]
                strategy="treatment-policy",
                _config=KnotConfig(id="e"),
            )

    def test_rejects_invalid_strategy(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="strategy"):
                EstimandAlignedAnalyzer(
                    records=r,
                    strategy="not-a-real-strategy",
                    _config=KnotConfig(id="e"),
                )

    def test_rejects_non_string_strategy(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(TypeError, match="strategy"):
                EstimandAlignedAnalyzer(
                    records=r,
                    strategy=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="e"),
                )

    def test_rejects_non_sequence_intercurrent_codes(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(TypeError, match="intercurrent_event_codes"):
                EstimandAlignedAnalyzer(
                    records=r,
                    strategy="while-on-treatment",
                    intercurrent_event_codes=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="e"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_treatment_policy_returns_input_unchanged(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            EstimandAlignedAnalyzer(
                records=r,
                strategy="treatment-policy",
                intercurrent_event_codes=("DISCONT",),
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert len(out) == 2

    async def test_while_on_treatment_excludes_intercurrent(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            EstimandAlignedAnalyzer(
                records=r,
                strategy="while-on-treatment",
                intercurrent_event_codes=("DISCONT",),
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert len(out) == 1
        assert out[0].observation_codes == ("AE001",)

    async def test_hypothetical_filters_intercurrent(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            EstimandAlignedAnalyzer(
                records=r,
                strategy="hypothetical",
                intercurrent_event_codes=("DISCONT",),
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert len(out) == 1

    async def test_principal_stratum_returns_input_unchanged(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            EstimandAlignedAnalyzer(
                records=r,
                strategy="principal-stratum",
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert len(out) == 2

    async def test_composite_strategy_returns_input_unchanged(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            EstimandAlignedAnalyzer(
                records=r,
                strategy="composite-strategy",
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert len(out) == 2
