"""Unit tests for :class:`MudLoggingIngester`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.mud_logging_ingester import MudLoggingIngester
from pirn.tapestry import Tapestry


class _MudLogSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "header": {"well_name": "Well-A"},
            "data": [
                {"depth_ft": 1000.0, "rop_ft_hr": 25.0, "gas_units": 50.0},
                {"depth_ft": 1001.0, "rop_ft_hr": 22.0, "gas_units": 45.0},
            ],
        }


class _MissingCurveSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "header": {"well_name": "Well-B"},
            "data": [{"depth_ft": 1000.0}],
        }


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_parsed_mud_log(self) -> None:
        with Tapestry() as t:
            src = _MudLogSource(_config=KnotConfig(id="src"))
            MudLoggingIngester(raw_mud_log=src, _config=KnotConfig(id="mli"))
        result = await t.run(RunRequest())
        out = result.outputs["mli"]
        assert out["well_name"] == "Well-A"
        assert out["record_count"] == 2
        assert "depth_ft" in out["curves"]

    async def test_records_error_on_missing_required_curve(self) -> None:
        with Tapestry() as t:
            src = _MissingCurveSource(_config=KnotConfig(id="src"))
            MudLoggingIngester(raw_mud_log=src, _config=KnotConfig(id="mli"))
        result = await t.run(RunRequest())
        assert any(e.exc_type == "ValueError" for e in result.exceptions)
