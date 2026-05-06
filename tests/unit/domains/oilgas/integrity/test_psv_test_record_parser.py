"""Unit tests for :class:`PSVTestRecordParser`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.psv_test_record_parser import PSVTestRecordParser

_FULL_RECORD: dict[str, Any] = {
    "tag": "PSV-101",
    "set_pressure_psi": 150.0,
    "test_date": "2026-01-15",
    "pass_fail": "pass",
}
_MISSING_FIELD_RECORD: dict[str, Any] = {"tag": "PSV-101"}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, required_fields: tuple = ("tag", "set_pressure_psi", "test_date", "pass_fail")) -> PSVTestRecordParser:
        return PSVTestRecordParser(
            raw_record=None,  # type: ignore[arg-type]
            required_fields=required_fields,
            _config=KnotConfig(id="psv", validate_io=False),
        )

    async def test_returns_parsed_record(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            raw_record=_FULL_RECORD,
            required_fields=("tag", "set_pressure_psi", "test_date", "pass_fail"),
        )
        assert out["parsed"] is True
        assert out["tag"] == "PSV-101"

    async def test_raises_on_missing_fields(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                raw_record=_MISSING_FIELD_RECORD,
                required_fields=("tag", "set_pressure_psi", "test_date", "pass_fail"),
            )
