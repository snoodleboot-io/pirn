"""Entry point: ``python -m examples.pipeline_composition.sub_tapestry``."""

import asyncio

from examples.pipeline_composition.sub_tapestry.sub_tapestry_example import SubTapestryExample

if __name__ == "__main__":
    asyncio.run(SubTapestryExample.main())
