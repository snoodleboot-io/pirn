"""Unit tests for :class:`MudLoggingIngester`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.well.mud_logging_ingester import MudLoggingIngester

_MUD_LOG: dict[str, Any] = {
    "header": {"well_name": "Well-A"},
    "data": [
        {"depth_ft": 1000.0, "rop_ft_hr": 25.0, "gas_units": 50.0},
        {"depth_ft": 1001.0, "rop_ft_hr": 22.0, "gas_units": 45.0},
    ],
}
_MISSING_CURVE_LOG: dict[str, Any] = {
    "header": {"well_name": "Well-B"},
    "data": [{"depth_ft": 1000.0}],
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MudLoggingIngester:
        return MudLoggingIngester(
            raw_mud_log=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="mli", validate_io=False),
        )

    async def test_returns_parsed_mud_log(self) -> None:
        knot = self._make_knot()
        out = await knot.process(raw_mud_log=_MUD_LOG)
        assert out["well_name"] == "Well-A"
        assert out["record_count"] == 2
        assert "depth_ft" in out["curves"]

    async def test_raises_on_missing_required_curve(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(raw_mud_log=_MISSING_CURVE_LOG)

    async def test_raises_on_missing_data_key(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "data"):
            await knot.process(raw_mud_log={"header": {"well_name": "Well-X"}})

    async def test_raises_on_missing_header_key(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "header"):
            await knot.process(raw_mud_log={"data": []})
