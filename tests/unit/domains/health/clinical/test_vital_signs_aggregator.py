"""Unit tests for :class:`VitalSignsAggregator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn_health.clinical.vital_signs_aggregator import (
    VitalSignsAggregator,
)

_CFG = KnotConfig(id="a")
_KNOT = VitalSignsAggregator(rows=[], _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "rows"):
            await _KNOT.process(rows=42)  # type: ignore[arg-type]

    async def test_rejects_non_mapping_row(self) -> None:
        with self.assertRaisesRegex(TypeError, "row"):
            await _KNOT.process(rows=["x"])  # type: ignore[list-item]

    async def test_raises_on_missing_patient_id(self) -> None:
        with self.assertRaisesRegex(KeyError, "patient_id"):
            await _KNOT.process(rows=[{"vital_name": "hr", "value": 70.0}])

    async def test_raises_on_missing_vital_name(self) -> None:
        with self.assertRaisesRegex(KeyError, "vital_name"):
            await _KNOT.process(rows=[{"patient_id": "P1", "value": 70.0}])

    async def test_raises_on_missing_value(self) -> None:
        with self.assertRaisesRegex(KeyError, "value"):
            await _KNOT.process(rows=[{"patient_id": "P1", "vital_name": "hr"}])

    async def test_raises_on_non_numeric_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "numeric"):
            await _KNOT.process(rows=[{"patient_id": "P1", "vital_name": "hr", "value": "bad"}])

    async def test_aggregates_per_patient(self) -> None:
        rows = (
            {"patient_id": "P1", "vital_name": "hr", "value": 70.0},
            {"patient_id": "P1", "vital_name": "hr", "value": 80.0},
        )
        out = await _KNOT.process(rows=rows)
        assert isinstance(out, Mapping)
        assert "P1" in out
        assert "hr" in out["P1"]
        assert out["P1"]["hr"]["max"] == 80.0
        assert out["P1"]["hr"]["min"] == 70.0
