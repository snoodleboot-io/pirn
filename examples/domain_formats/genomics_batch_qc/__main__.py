"""Entry point: ``python -m examples.domain_formats.genomics_batch_qc``."""

import asyncio

from examples.domain_formats.genomics_batch_qc.genomics_batch_qc import GenomicsBatchQc

if __name__ == "__main__":
    asyncio.run(GenomicsBatchQc.main())
