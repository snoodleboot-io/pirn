"""Unit tests for :class:`EncounterTimelineAssembler`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.encounter_timeline_assembler import (
    EncounterTimelineAssembler,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "records"):
            EncounterTimelineAssembler(
                records=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="a"),
            )

    def test_rejects_non_record(self) -> None:
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            EncounterTimelineAssembler(
                records=["x"],  # type: ignore[list-item]
                _config=KnotConfig(id="a"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_groups_and_sorts_by_time(self) -> None:
        early = datetime(2026, 1, 1, tzinfo=timezone.utc)
        late = datetime(2026, 2, 1, tzinfo=timezone.utc)
        records = (
            ClinicalRecord(patient_id="P1", observed_at=late),
            ClinicalRecord(patient_id="P1", observed_at=early),
            ClinicalRecord(patient_id="P2", observed_at=late),
        )
        with Tapestry() as t:
            EncounterTimelineAssembler(
                records=records,
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"P1", "P2"}
        assert out["P1"][0].observed_at == early
