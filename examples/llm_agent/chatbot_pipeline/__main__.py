"""Entry point: ``python -m examples.llm_agent.chatbot_pipeline``."""

import asyncio

from examples.llm_agent.chatbot_pipeline.chatbot_pipeline import ChatbotPipeline

if __name__ == "__main__":
    asyncio.run(ChatbotPipeline.main())
