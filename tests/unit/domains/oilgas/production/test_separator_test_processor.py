"""Unit tests for :class:`SeparatorTestProcessor`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.separator_test_processor import (
    SeparatorTestProcessor,
)
from pirn.tapestry import Tapestry


class _TestDataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "oil_rate_bopd": 500.0,
            "gas_rate_mmscfd": 0.5,
            "water_rate_bwpd": 200.0,
            "separator_pressure_psig": 100.0,
            "separator_temp_f": 80.0,
        }


class TestConstruction:
    def test_rejects_invalid_stages(self) -> None:
        with pytest.raises(ValueError, match="separator_stages"):
            with Tapestry():
                src = _TestDataSource(_config=KnotConfig(id="src"))
                SeparatorTestProcessor(
                    test_data=src,
                    separator_stages=4,
                    _config=KnotConfig(id="stp"),
                )

    def test_rejects_non_int_stages(self) -> None:
        with pytest.raises(TypeError, match="separator_stages"):
            with Tapestry():
                src = _TestDataSource(_config=KnotConfig(id="src"))
                SeparatorTestProcessor(
                    test_data=src,
                    separator_stages=2.0,  # type: ignore[arg-type]
                    _config=KnotConfig(id="stp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_gor_wor_shrinkage(self) -> None:
        with Tapestry() as t:
            src = _TestDataSource(_config=KnotConfig(id="src"))
            SeparatorTestProcessor(
                test_data=src, separator_stages=2, _config=KnotConfig(id="stp")
            )
        result = await t.run(RunRequest())
        out = result.outputs["stp"]
        assert "gor_scf_bbl" in out
        assert "wor_bbl_bbl" in out
        assert "oil_shrinkage_factor" in out
        assert out["gor_scf_bbl"] > 0.0
