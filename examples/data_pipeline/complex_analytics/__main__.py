"""Entry point: ``python -m examples.data_pipeline.complex_analytics``."""

import asyncio

from examples.data_pipeline.complex_analytics.complex_analytics import ComplexAnalytics

if __name__ == "__main__":
    asyncio.run(ComplexAnalytics.main())
