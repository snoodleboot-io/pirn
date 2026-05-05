"""Unit tests for :class:`ADaMDatasetBuilder`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.trials.adam_dataset_builder import ADaMDatasetBuilder
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord
from pirn.tapestry import Tapestry


@knot
async def emit_records() -> Sequence[ClinicalTrialRecord]:
    return (
        ClinicalTrialRecord(
            trial_id="T-1",
            subject_id="S-1",
            visit_number=2,
            observed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_records(self) -> None:
        with self.assertRaisesRegex(TypeError, "records"):
            ADaMDatasetBuilder(
                records="not-a-knot",  # type: ignore[arg-type]
                target_dataset="ADSL",
                derivations={"AVISITN": "visit_number"},
                _config=KnotConfig(id="b"),
            )

    def test_rejects_empty_target_dataset(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "target_dataset"):
                ADaMDatasetBuilder(
                    records=r,
                    target_dataset="",
                    derivations={"AVISITN": "visit_number"},
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_empty_derivations(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "derivations"):
                ADaMDatasetBuilder(
                    records=r,
                    target_dataset="ADSL",
                    derivations={},
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_string_derivation_value(self) -> None:
        with Tapestry():
            r = emit_records(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "derivation values"):
                ADaMDatasetBuilder(
                    records=r,
                    target_dataset="ADSL",
                    derivations={"AVISITN": 42},  # type: ignore[dict-item]
                    _config=KnotConfig(id="b"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_rows_with_derivations(self) -> None:
        with Tapestry() as t:
            r = emit_records(_config=KnotConfig(id="r"))
            ADaMDatasetBuilder(
                records=r,
                target_dataset="ADSL",
                derivations={"AVISITN": "visit_number"},
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["trial_id"] == "T-1"
        assert out[0]["subject_id"] == "S-1"
        assert out[0]["AVISITN"] == 2
