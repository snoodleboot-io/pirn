"""Unit tests for :class:`MudLogAssembler`."""

from __future__ import annotations

import json
import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.assemblers.mud_log_assembler import MudLogAssembler


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make() -> MudLogAssembler:
    return MudLogAssembler(
        body=_body_param(),
        _config=KnotConfig(id="assembler"),
    )


_VALID_BODY = json.dumps({
    "header": {"well_name": "WX-1"},
    "data": [
        {"depth_ft": 1000.0, "rop_ft_hr": 50.0, "gas_units": 120.0},
        {"depth_ft": 1001.0, "rop_ft_hr": 48.5, "gas_units": 115.0},
    ],
}).encode()


class TestMudLogAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_dict(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert isinstance(result, dict)

    async def test_well_name_populated(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result["well_name"] == "WX-1"

    async def test_record_count_matches(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert result["record_count"] == 2

    async def test_curves_list_populated(self) -> None:
        knot = _make()
        result = await knot.process(body=_VALID_BODY)
        assert "depth_ft" in result["curves"]

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
        body = json.dumps({
            "header": {"well_name": "WX-1"},
            "data": [{"depth_ft": 1000.0}],
        }).encode()
        with pytest.raises(ValueError, match="missing required curves"):
            await knot.process(body=body)
