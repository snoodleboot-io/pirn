"""Run the agent tapestry defined in tapestry.yaml.

Demonstrates that an agentic pipeline authored as a core YAML document (no
agents-only schema) loads and runs exactly like any other pirn pipeline (ADR
agents-speaks-core WS6a).

Run with:
    uv run python examples/agents_core_pipeline/run.py
"""

from __future__ import annotations

import asyncio

from pirn.core.run_request import RunRequest

from pirn_agents.types.messaging.agent_message import AgentMessage

from build_tapestry import build_tapestry


async def main() -> None:
    tapestry = build_tapestry()
    seed = (AgentMessage(role="user", content="What is the capital of France?"),)
    result = await tapestry.run(RunRequest(parameters={"seed_messages": seed}))
    for rec in result.lineage:
        print(f"  {rec.knot_id:<18} {rec.outcome}")
    print(result.outputs["agent"].content)


if __name__ == "__main__":
    asyncio.run(main())
