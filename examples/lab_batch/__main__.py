"""Entry point: ``python -m examples.lab_batch``."""

import asyncio

from examples.lab_batch.lab_batch import LabBatch

if __name__ == "__main__":
    asyncio.run(LabBatch.main())
