"""Unit tests for :class:`Scope1EmissionsReporter`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.scope1_emissions_reporter import (
    Scope1EmissionsReporter,
)
from pirn.tapestry import Tapestry


class _EventsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"source_type": "flaring", "volume_mcf": 100.0, "gas_type": "ch4"},
            {"source_type": "venting", "volume_mcf": 50.0, "gas_type": "co2"},
        ]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_dict_factors(self) -> None:
        with self.assertRaisesRegex(TypeError, "co2_eq_factors"):
            with Tapestry():
                src = _EventsSource(_config=KnotConfig(id="src"))
                Scope1EmissionsReporter(
                    events=src,
                    co2_eq_factors="not_a_dict",  # type: ignore[arg-type]
                    _config=KnotConfig(id="s1"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_emissions_report(self) -> None:
        with Tapestry() as t:
            src = _EventsSource(_config=KnotConfig(id="src"))
            Scope1EmissionsReporter(events=src, _config=KnotConfig(id="s1"))
        result = await t.run(RunRequest())
        out = result.outputs["s1"]
        assert out["event_count"] == 2
        assert isinstance(out["total_co2e_tonnes"], float)
        assert isinstance(out["sources"], list)

    async def test_empty_events(self) -> None:
        class _EmptySource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> list[dict[str, Any]]:
                return []

        with Tapestry() as t:
            src = _EmptySource(_config=KnotConfig(id="src"))
            Scope1EmissionsReporter(events=src, _config=KnotConfig(id="s1"))
        result = await t.run(RunRequest())
        out = result.outputs["s1"]
        assert out["event_count"] == 0
        assert out["total_co2e_tonnes"] == 0.0
