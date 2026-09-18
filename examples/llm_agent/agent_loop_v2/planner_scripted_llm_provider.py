"""``PlannerScriptedLLMProvider`` — the scripted LLM double the ``Planner`` knot reads.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import ClassVar

from examples.llm_agent.agent_loop_v2.scripted_llm_provider import ScriptedLLMProvider


class PlannerScriptedLLMProvider(ScriptedLLMProvider):
    """LLM stub for the Planner knot.

    Emits numbered steps that begin with a tool name so ``ToolRouter``
    can match them via substring search.  Lines not starting with ``#``
    become plan steps in ``Planner``.
    """

    _pool: ClassVar[tuple[str, ...]] = (
        "1. calculate: compound interest on the principal amount\n"
        "2. lookup: applicable policy terms and conditions",
        "1. search: recent developments and key findings\n2. calculate: estimated impact figures",
        "1. lookup: existing knowledge base entries\n2. search: supplementary external sources",
        "1. calculate: cost projections for the period\n2. lookup: pricing and billing details",
        "1. search: authoritative references on the topic\n"
        "2. lookup: internal policy documentation",
    )
