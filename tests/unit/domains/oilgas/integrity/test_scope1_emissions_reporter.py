"""Unit tests for :class:`Scope1EmissionsReporter`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.scope1_emissions_reporter import (
    Scope1EmissionsReporter,
)

_EVENTS: list[dict[str, Any]] = [
    {"source_type": "flaring", "volume_mcf": 100.0, "gas_type": "ch4"},
    {"source_type": "venting", "volume_mcf": 50.0, "gas_type": "co2"},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> Scope1EmissionsReporter:
        return Scope1EmissionsReporter(
            events=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="s1", validate_io=False),
        )

    async def test_rejects_non_dict_factors(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "co2_eq_factors"):
            await knot.process(events=_EVENTS, co2_eq_factors="not_a_dict")  # type: ignore[arg-type]

    async def test_returns_emissions_report(self) -> None:
        knot = self._make_knot()
        out = await knot.process(events=_EVENTS)
        assert out["event_count"] == 2
        assert isinstance(out["total_co2e_tonnes"], float)
        assert isinstance(out["sources"], list)

    async def test_empty_events(self) -> None:
        knot = self._make_knot()
        out = await knot.process(events=[])
        assert out["event_count"] == 0
        assert out["total_co2e_tonnes"] == 0.0
