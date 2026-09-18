"""Entry point: ``python -m examples.data_pipeline.simple_etl``."""

import asyncio

from examples.data_pipeline.simple_etl.simple_etl import SimpleEtl

if __name__ == "__main__":
    asyncio.run(SimpleEtl.main())
