"""Unit tests for :class:`ADaMDatasetBuilder`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.trials.adam_dataset_builder import ADaMDatasetBuilder
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="b")
_RECORDS: tuple[ClinicalTrialRecord, ...] = (
    ClinicalTrialRecord(
        trial_id="T-1",
        subject_id="S-1",
        visit_number=2,
        observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ),
)
_DERIVATIONS = {"AVISITN": "visit_number"}


def _make_knot() -> ADaMDatasetBuilder:
    with Tapestry():
        src = Parameter("rec", tuple, default=_RECORDS, _config=KnotConfig(id="rec"))
        return ADaMDatasetBuilder(
            records=src,
            target_dataset="ADSL",
            derivations=_DERIVATIONS,
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_target_dataset(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "target_dataset"):
            await knot.process(records=_RECORDS, target_dataset="", derivations=_DERIVATIONS)

    async def test_rejects_empty_derivations(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "derivations"):
            await knot.process(records=_RECORDS, target_dataset="ADSL", derivations={})

    async def test_rejects_non_string_derivation_value(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "derivation values"):
            await knot.process(records=_RECORDS, target_dataset="ADSL", derivations={"AVISITN": 42})  # type: ignore[dict-item]

    async def test_emits_rows_with_derivations(self) -> None:
        knot = _make_knot()
        out = await knot.process(records=_RECORDS, target_dataset="ADSL", derivations=_DERIVATIONS)
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["trial_id"] == "T-1"
        assert out[0]["subject_id"] == "S-1"
        assert out[0]["AVISITN"] == 2
