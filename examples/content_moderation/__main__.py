"""Entry point: ``python -m examples.content_moderation``."""

import asyncio

from examples.content_moderation.content_moderation import ContentModeration

if __name__ == "__main__":
    asyncio.run(ContentModeration.main())
