"""Entry point: ``python -m examples.llm_agent.agent_loop``."""

import asyncio

from examples.llm_agent.agent_loop.agent_loop import AgentLoop

if __name__ == "__main__":
    asyncio.run(AgentLoop.main())
