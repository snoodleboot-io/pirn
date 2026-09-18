"""Entry point: ``python -m examples.software_execution.request_handler``."""

import asyncio

from examples.software_execution.request_handler.request_handler import RequestHandler

if __name__ == "__main__":
    asyncio.run(RequestHandler.main())
