"""Entry point: ``python -m examples.domain_formats.hl7v2_message_router``."""

import asyncio

from examples.domain_formats.hl7v2_message_router.hl7v2_message_router import Hl7v2MessageRouter

if __name__ == "__main__":
    asyncio.run(Hl7v2MessageRouter.main())
