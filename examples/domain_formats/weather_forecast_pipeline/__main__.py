"""Entry point: ``python -m examples.domain_formats.weather_forecast_pipeline``."""

import asyncio

from examples.domain_formats.weather_forecast_pipeline.weather_forecast_pipeline import (
    WeatherForecastPipeline,
)

if __name__ == "__main__":
    asyncio.run(WeatherForecastPipeline.main())
