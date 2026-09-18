"""Entry point: ``python -m examples.software_execution.ci_pipeline``."""

import asyncio

from examples.software_execution.ci_pipeline.ci_pipeline import CiPipeline

if __name__ == "__main__":
    asyncio.run(CiPipeline.main())
