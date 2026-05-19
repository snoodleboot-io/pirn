"""Unit tests for :class:`LabResultNormalizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.lab_result_normalizer import (
    LabResultNormalizer,
)

_CFG = KnotConfig(id="n")
_KNOT = LabResultNormalizer(rows=[], unit_conversions={}, target_unit="mg/dL", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_rows(self) -> None:
        with self.assertRaisesRegex(TypeError, "rows"):
            await _KNOT.process(rows=42, unit_conversions={}, target_unit="mg/dL")  # type: ignore[arg-type]

    async def test_rejects_non_mapping_conversions(self) -> None:
        with self.assertRaisesRegex(TypeError, "unit_conversions"):
            await _KNOT.process(rows=[], unit_conversions=42, target_unit="mg/dL")  # type: ignore[arg-type]

    async def test_rejects_non_string_target_unit(self) -> None:
        with self.assertRaisesRegex(TypeError, "target_unit"):
            await _KNOT.process(rows=[], unit_conversions={}, target_unit=42)  # type: ignore[arg-type]

    async def test_rejects_empty_target_unit(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _KNOT.process(rows=[], unit_conversions={}, target_unit="")

    async def test_returns_tuple(self) -> None:
        out = await _KNOT.process(
            rows=[{"value": 100.0, "unit": "mg/dL"}],
            unit_conversions={("mg/dL", "mmol/L"): 0.0555},
            target_unit="mmol/L",
        )
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["unit"] == "mmol/L"

    async def test_raises_on_missing_unit_field(self) -> None:
        with self.assertRaisesRegex(KeyError, "unit"):
            await _KNOT.process(
                rows=[{"value": 100.0}],
                unit_conversions={},
                target_unit="mg/dL",
            )

    async def test_raises_on_missing_value_field(self) -> None:
        with self.assertRaisesRegex(KeyError, "value"):
            await _KNOT.process(
                rows=[{"unit": "mg/dL"}],
                unit_conversions={},
                target_unit="mg/dL",
            )

    async def test_raises_on_non_numeric_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "numeric"):
            await _KNOT.process(
                rows=[{"unit": "mg/dL", "value": "bad"}],
                unit_conversions={},
                target_unit="mg/dL",
            )
