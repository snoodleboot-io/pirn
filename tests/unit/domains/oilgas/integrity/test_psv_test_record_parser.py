"""Unit tests for :class:`PSVTestRecordParser`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.psv_test_record_parser import PSVTestRecordParser
from pirn.tapestry import Tapestry


class _RecordSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "tag": "PSV-101",
            "set_pressure_psi": 150.0,
            "test_date": "2026-01-15",
            "pass_fail": "pass",
        }


class _MissingFieldSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"tag": "PSV-101"}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_record(self) -> None:
        with Tapestry() as t:
            src = _RecordSource(_config=KnotConfig(id="src"))
            PSVTestRecordParser(raw_record=src, _config=KnotConfig(id="psv"))
        result = await t.run(RunRequest())
        out = result.outputs["psv"]
        assert out["parsed"] is True
        assert out["tag"] == "PSV-101"

    async def test_records_error_on_missing_fields(self) -> None:
        with Tapestry() as t:
            src = _MissingFieldSource(_config=KnotConfig(id="src"))
            PSVTestRecordParser(raw_record=src, _config=KnotConfig(id="psv"))
        result = await t.run(RunRequest())
        assert any(e.exc_type == "ValueError" for e in result.exceptions)
