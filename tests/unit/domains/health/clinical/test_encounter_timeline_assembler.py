"""Unit tests for :class:`EncounterTimelineAssembler`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn_health.clinical.encounter_timeline_assembler import (
    EncounterTimelineAssembler,
)
from pirn_health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="a")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        knot = EncounterTimelineAssembler(records=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42)  # type: ignore[arg-type]

    async def test_rejects_non_record(self) -> None:
        knot = EncounterTimelineAssembler(records=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(records=["x"])  # type: ignore[list-item]

    async def test_groups_and_sorts_by_time(self) -> None:
        early = datetime(2026, 1, 1, tzinfo=UTC)
        late = datetime(2026, 2, 1, tzinfo=UTC)
        records = (
            ClinicalRecord(patient_id="P1", observed_at=late),
            ClinicalRecord(patient_id="P1", observed_at=early),
            ClinicalRecord(patient_id="P2", observed_at=late),
        )
        knot = EncounterTimelineAssembler(records=records, _config=_CFG)
        out = await knot.process(records=records)
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"P1", "P2"}
        assert out["P1"][0].observed_at == early
