"""Entry point: ``python -m examples.agents_core_pipeline``."""

import asyncio

from examples.agents_core_pipeline.agents_core_pipeline import AgentsCorePipeline

if __name__ == "__main__":
    asyncio.run(AgentsCorePipeline.main())
