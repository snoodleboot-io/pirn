"""Entry point: ``python -m examples.domain_formats.geospatial_layer_analysis``."""

import asyncio

from examples.domain_formats.geospatial_layer_analysis.geospatial_layer_analysis import (
    GeospatialLayerAnalysis,
)

if __name__ == "__main__":
    asyncio.run(GeospatialLayerAnalysis.main())
