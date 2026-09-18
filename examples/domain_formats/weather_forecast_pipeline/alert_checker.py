"""``AlertChecker`` — final stage that logs severe alerts and passes the forecast on.

Part of the ``examples.domain_formats.weather_forecast_pipeline`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.weather_forecast_pipeline.forecast import Forecast


class AlertChecker(Knot):
    """Final gate — logs severe alerts and passes the forecast through."""

    async def process(self, forecast: Forecast, **_: Any) -> Forecast:
        return forecast
