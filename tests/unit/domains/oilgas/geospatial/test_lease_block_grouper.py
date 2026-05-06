"""Unit tests for :class:`LeaseBlockGrouper`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.geospatial.lease_block_grouper import LeaseBlockGrouper
from pirn.tapestry import Tapestry

_LOC: dict[str, Any] = {"well_id": "W", "x": 0.0, "y": 0.0}


def _make_knot(lease_block_id: str = "LB-1") -> LeaseBlockGrouper:
    with Tapestry():
        loc = Parameter("loc", dict, default={}, _config=KnotConfig(id="loc"))
        return LeaseBlockGrouper(
            location=loc,
            lease_block_id=lease_block_id,
            _config=KnotConfig(id="lb"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_block_id(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "lease_block_id"):
            await knot.process(location=_LOC, lease_block_id="")

    async def test_appends_lease_block(self) -> None:
        knot = _make_knot(lease_block_id="LB-1")
        out = await knot.process(location=_LOC, lease_block_id="LB-1")
        assert out["well_id"] == "W"
        assert out["lease_block_id"] == "LB-1"

    async def test_preserves_existing_fields(self) -> None:
        knot = _make_knot(lease_block_id="LB-99")
        out = await knot.process(location=_LOC, lease_block_id="LB-99")
        assert out["x"] == 0.0
        assert out["y"] == 0.0
