"""Entry point: ``python -m examples.data_pipeline.transport_layers``."""

import asyncio

from examples.data_pipeline.transport_layers.transport_layers import TransportLayers

if __name__ == "__main__":
    asyncio.run(TransportLayers.main())
