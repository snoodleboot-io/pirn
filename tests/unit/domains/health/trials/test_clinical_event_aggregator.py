"""Unit tests for :class:`ClinicalEventAggregator`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.clinical_event_aggregator import (
    ClinicalEventAggregator,
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
            observation_codes=("AE001", "AE002"),
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-1",
            visit_number=2,
            observation_codes=("AE001",),
            observed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        ),
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-2",
            visit_number=1,
            observation_codes=("AE002",),
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
    )


class TestConstruction:
    def test_rejects_non_knot_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            ClinicalEventAggregator(
                records="not-a-knot",  # type: ignore[arg-type]
                event_codes=("AE001",),
                _config=KnotConfig(id="a"),
            )

    def test_rejects_non_sequence_event_codes(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(TypeError, match="event_codes"):
                ClinicalEventAggregator(
                    records=r,
                    event_codes=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_event_codes(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="event_codes"):
                ClinicalEventAggregator(
                    records=r,
                    event_codes=(),
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_blank_event_code(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="event_code"):
                ClinicalEventAggregator(
                    records=r,
                    event_codes=("",),
                    _config=KnotConfig(id="a"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_aggregates_per_subject_per_event(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            ClinicalEventAggregator(
                records=r,
                event_codes=("AE001", "AE002"),
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, Mapping)
        assert out["S-1"]["AE001"] == 2
        assert out["S-1"]["AE002"] == 1
        assert out["S-2"]["AE001"] == 0
        assert out["S-2"]["AE002"] == 1
