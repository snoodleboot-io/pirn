"""Unit tests for :class:`ScadaHistorianIngester`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.scada_historian_ingester import (
    ScadaHistorianIngester,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_historian_connection(
        self, fixed_since: datetime
    ) -> None:
        with pytest.raises(TypeError, match="connection"):
            ScadaHistorianIngester(
                connection="not-a-conn",  # type: ignore[arg-type]
                tag="tag",
                since=fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_empty_tag(
        self, stub_historian: object, fixed_since: datetime
    ) -> None:
        with pytest.raises(ValueError, match="tag"):
            ScadaHistorianIngester(
                connection=stub_historian,  # type: ignore[arg-type]
                tag="",
                since=fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_datetime_since(self, stub_historian: object) -> None:
        with pytest.raises(TypeError, match="since"):
            ScadaHistorianIngester(
                connection=stub_historian,  # type: ignore[arg-type]
                tag="tag",
                since="2026-01-01",  # type: ignore[arg-type]
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_interval(
        self, stub_historian: object, fixed_since: datetime
    ) -> None:
        with pytest.raises(ValueError, match="sample_interval_sec"):
            ScadaHistorianIngester(
                connection=stub_historian,  # type: ignore[arg-type]
                tag="tag",
                since=fixed_since,
                sample_interval_sec=0.0,
                _config=KnotConfig(id="i"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_series(
        self, stub_historian: object, fixed_since: datetime
    ) -> None:
        with Tapestry() as t:
            ScadaHistorianIngester(
                connection=stub_historian,  # type: ignore[arg-type]
                tag="P:WELL1.OILRATE",
                since=fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "P:WELL1.OILRATE"
        assert out.sample_interval_sec == 60.0
