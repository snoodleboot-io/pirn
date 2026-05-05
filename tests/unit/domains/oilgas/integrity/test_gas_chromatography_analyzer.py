"""Unit tests for :class:`GasChromatographyAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.gas_chromatography_analyzer import (
    GasChromatographyAnalyzer,
)
from pirn.tapestry import Tapestry


class _GCReportSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "components": [
                {"name": "methane", "area_percent": 90.0},
                {"name": "ethane", "area_percent": 10.0},
            ],
            "total_area": 100.0,
        }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_bool_normalize(self) -> None:
        with self.assertRaisesRegex(TypeError, "normalize_fractions"):
            with Tapestry():
                src = _GCReportSource(_config=KnotConfig(id="src"))
                GasChromatographyAnalyzer(
                    gc_report=src,
                    normalize_fractions="yes",  # type: ignore[arg-type]
                    _config=KnotConfig(id="gc"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_mole_fractions(self) -> None:
        with Tapestry() as t:
            src = _GCReportSource(_config=KnotConfig(id="src"))
            GasChromatographyAnalyzer(
                gc_report=src,
                _config=KnotConfig(id="gc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["gc"]
        assert "mole_fractions" in out
        assert "gross_heating_value_btu_scf" in out
        assert "specific_gravity" in out

    async def test_records_error_on_non_dict_report(self) -> None:
        class _BadSource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> list[Any]:
                return []

        with Tapestry() as t:
            src = _BadSource(_config=KnotConfig(id="src"))
            GasChromatographyAnalyzer(
                gc_report=src,
                _config=KnotConfig(id="gc"),
            )
        result = await t.run(RunRequest())
        assert result.exceptions
