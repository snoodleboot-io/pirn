"""Unit tests for :class:`RelativePermeabilityModeler`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.relative_permeability_modeler import (
    RelativePermeabilityModeler,
)
from pirn.domains.oilgas.types.pvt_table import PVTTable
from pirn.tapestry import Tapestry


class _PvtSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> PVTTable:
        return PVTTable(fluid_id="f")


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                pvt = _PvtSource(_config=KnotConfig(id="src"))
                RelativePermeabilityModeler(
                    pvt=pvt,
                    method="bogus",
                    _config=KnotConfig(id="rp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_kr_params(self) -> None:
        with Tapestry() as t:
            pvt = _PvtSource(_config=KnotConfig(id="src"))
            RelativePermeabilityModeler(
                pvt=pvt,
                method="corey",
                _config=KnotConfig(id="rp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rp"]
        assert out["fluid_id"] == "f"
        assert out["method"] == "corey"
