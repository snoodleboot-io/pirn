"""Unit tests for :class:`DowntimeEventClassifier`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.downtime_event_classifier import (
    DowntimeEventClassifier,
)
from pirn.tapestry import Tapestry


class _SeriesSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"timestamp_iso": "2026-01-01T00:00:00Z", "rate_bopd": 100.0},
            {"timestamp_iso": "2026-01-02T00:00:00Z", "rate_bopd": 0.0},
            {"timestamp_iso": "2026-01-03T00:00:00Z", "rate_bopd": 0.0},
            {"timestamp_iso": "2026-01-04T00:00:00Z", "rate_bopd": 80.0},
        ]


class TestConstruction:
    def test_rejects_zero_threshold(self) -> None:
        with pytest.raises(ValueError, match="gap_threshold_hours"):
            with Tapestry():
                src = _SeriesSource(_config=KnotConfig(id="src"))
                DowntimeEventClassifier(
                    production_series=src,
                    gap_threshold_hours=0.0,
                    _config=KnotConfig(id="dec"),
                )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="gap_threshold_hours"):
            with Tapestry():
                src = _SeriesSource(_config=KnotConfig(id="src"))
                DowntimeEventClassifier(
                    production_series=src,
                    gap_threshold_hours="4",  # type: ignore[arg-type]
                    _config=KnotConfig(id="dec"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_detects_downtime_event(self) -> None:
        with Tapestry() as t:
            src = _SeriesSource(_config=KnotConfig(id="src"))
            DowntimeEventClassifier(
                production_series=src,
                gap_threshold_hours=4.0,
                _config=KnotConfig(id="dec"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["dec"]
        assert isinstance(out, list)
        assert len(out) == 1
        assert "start_iso" in out[0]
        assert "category" in out[0]

    async def test_returns_empty_list_for_no_gaps(self) -> None:
        class _NoGaps(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> list[dict[str, Any]]:
                return [
                    {"timestamp_iso": "2026-01-01T00:00:00Z", "rate_bopd": 100.0},
                    {"timestamp_iso": "2026-01-02T00:00:00Z", "rate_bopd": 90.0},
                ]

        with Tapestry() as t:
            src = _NoGaps(_config=KnotConfig(id="src"))
            DowntimeEventClassifier(
                production_series=src,
                gap_threshold_hours=4.0,
                _config=KnotConfig(id="dec"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["dec"] == []
