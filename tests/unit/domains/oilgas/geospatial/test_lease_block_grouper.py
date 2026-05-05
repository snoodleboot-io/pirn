"""Unit tests for :class:`LeaseBlockGrouper`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.lease_block_grouper import LeaseBlockGrouper
from pirn.tapestry import Tapestry


class _LocSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"well_id": "W", "x": 0.0, "y": 0.0}


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_block_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "lease_block_id"):
            with Tapestry():
                loc = _LocSource(_config=KnotConfig(id="loc"))
                LeaseBlockGrouper(
                    location=loc,
                    lease_block_id="",
                    _config=KnotConfig(id="lb"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_lease_block(self) -> None:
        with Tapestry() as t:
            loc = _LocSource(_config=KnotConfig(id="loc"))
            LeaseBlockGrouper(
                location=loc,
                lease_block_id="LB-1",
                _config=KnotConfig(id="lb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lb"]
        assert out["well_id"] == "W"
        assert out["lease_block_id"] == "LB-1"
