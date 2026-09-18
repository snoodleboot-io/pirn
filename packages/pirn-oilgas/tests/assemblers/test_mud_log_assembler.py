"""Unit tests for :class:`MudLogAssembler`."""

from __future__ import annotations

import json
import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_oilgas.assemblers.mud_log_assembler import MudLogAssembler
from pirn_oilgas.types.mud_log import MudLog
from pirn_oilgas.types.mud_log_payload import MudLogPayload


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make() -> MudLogAssembler:
    return MudLogAssembler(
        body=_body_param(),
        _config=KnotConfig(id="assembler"),
    )


_VALID_BODY = json.dumps(
    {
        "header": {"well_name": "WX-1"},
        "data": [
            {"depth_ft": 1000.0, "rop_ft_hr": 50.0, "gas_units": 120.0},
            {"depth_ft": 1001.0, "rop_ft_hr": 48.5, "gas_units": 115.0},
        ],
    }
).encode()


class TestMudLogAssembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_typed_payload(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert isinstance(result, MudLogPayload)
        assert isinstance(result.metadata, MudLog)

    async def test_well_name_populated(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result.metadata.well_name == "WX-1"

    async def test_record_count_matches(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result.metadata.record_count == 2
        assert len(result.data) == 2

    async def test_curves_populated(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result.metadata.curves == ("depth_ft", "rop_ft_hr", "gas_units")

    async def test_records_carry_the_decoded_values(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result.data[1]["rop_ft_hr"] == 48.5

    async def test_audit_dict_describes_the_log_without_the_rows(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        audit = result._pirn_audit_dict()
        assert audit["well_name"] == "WX-1"
        assert audit["record_count"] == 2
        assert "data" not in audit

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes")  # type: ignore[arg-type]

    async def test_rejects_invalid_json(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="not valid JSON"):
            await knot.process(body=b"not json {{{")

    async def test_rejects_missing_header_field(self) -> None:
        knot = _make()
        body = json.dumps({"data": []}).encode()
        with pytest.raises(ValueError, match="missing required field 'header'"):
            await knot.process(body=body)

    async def test_rejects_missing_required_curves(self) -> None:
        knot = _make()
        body = json.dumps(
            {
                "header": {"well_name": "WX-1"},
                "data": [{"depth_ft": 1000.0}],
            }
        ).encode()
        with pytest.raises(ValueError, match="missing required curves"):
            await knot.process(body=body)

    async def test_rejects_a_later_row_missing_a_required_curve(self) -> None:
        """Checking only the first row let the rest of the log through unvalidated."""
        knot = _make()
        body = json.dumps(
            {
                "header": {"well_name": "WX-1"},
                "data": [
                    {"depth_ft": 1000.0, "rop_ft_hr": 50.0, "gas_units": 120.0},
                    {"depth_ft": 1001.0, "rop_ft_hr": 48.5},
                ],
            }
        ).encode()
        with pytest.raises(ValueError, match="record 1"):
            await knot.process(body=body)

    async def test_rejects_a_nested_value(self) -> None:
        knot = _make()
        body = json.dumps(
            {
                "header": {"well_name": "WX-1"},
                "data": [
                    {"depth_ft": 1000.0, "rop_ft_hr": 50.0, "gas_units": {"c1": 1.0}},
                ],
            }
        ).encode()
        with pytest.raises(ValueError, match="not a number or a string"):
            await knot.process(body=body)

    async def test_rejects_an_invalid_depth_unit(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="depth_unit must be"):
            await knot.process(body=_VALID_BODY, depth_unit="fathoms")

    async def test_keeps_a_descriptive_curve_as_text(self) -> None:
        knot = _make()
        body = json.dumps(
            {
                "header": {"well_name": "WX-1"},
                "data": [
                    {
                        "depth_ft": 1000.0,
                        "rop_ft_hr": 50.0,
                        "gas_units": 120.0,
                        "lithology": "shale, grey",
                    }
                ],
            }
        ).encode()
        result = await knot.process(body=body)
        assert result.data[0]["lithology"] == "shale, grey"
