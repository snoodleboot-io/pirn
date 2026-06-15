"""Unit tests for :class:`WellCompletionObjectStoreAssembler`."""

from __future__ import annotations

import json
import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_oilgas.assemblers.well_completion_object_store_assembler import (
    WellCompletionObjectStoreAssembler,
)
from pirn_oilgas.types.drilling_parameters import DrillingParameters


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make(well_id: str = "W-01") -> WellCompletionObjectStoreAssembler:
    return WellCompletionObjectStoreAssembler(
        body=_body_param(),
        well_id=well_id,
        _config=KnotConfig(id="assembler"),
    )


_VALID_BODY = json.dumps({
    "perforations": [
        {"top_ft": 8500.0, "bottom_ft": 8520.0},
        {"top_ft": 8550.0, "bottom_ft": 8570.0},
    ]
}).encode()


class TestWellCompletionObjectStoreAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_drilling_parameters(self) -> None:
        knot = _make("W-01")
        result = await knot.process(body=_VALID_BODY, well_id="W-01")
        assert isinstance(result, DrillingParameters)

    async def test_well_id_matches(self) -> None:
        knot = _make("W-01")
        result = await knot.process(body=_VALID_BODY, well_id="W-01")
        assert result.well_id == "W-01"

    async def test_depth_count_from_perforations(self) -> None:
        knot = _make("W-01")
        result = await knot.process(body=_VALID_BODY, well_id="W-01")
        assert result.depth_count == 2

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes", well_id="W-01")  # type: ignore[arg-type]

    async def test_rejects_non_str_well_id(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="well_id must be str"):
            await knot.process(body=b"x", well_id=42)  # type: ignore[arg-type]

    async def test_rejects_empty_well_id(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="well_id must be non-empty"):
            await knot.process(body=b"x", well_id="")

    async def test_rejects_invalid_json(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="not valid JSON"):
            await knot.process(body=b"not json", well_id="W-01")
