"""Entry point: ``python -m examples.llm_agent.agent_loop_v2``."""

import asyncio

from examples.llm_agent.agent_loop_v2.agent_loop_v2 import AgentLoopV2

if __name__ == "__main__":
    asyncio.run(AgentLoopV2.main())
