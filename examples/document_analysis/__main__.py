"""Entry point: ``python -m examples.document_analysis``."""

import asyncio

from examples.document_analysis.document_analysis import DocumentAnalysis

if __name__ == "__main__":
    asyncio.run(DocumentAnalysis.main())
