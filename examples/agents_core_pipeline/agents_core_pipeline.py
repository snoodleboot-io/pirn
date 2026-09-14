"""Build and run the agent tapestry defined in ``tapestry.yaml``.

This is the ADR agents-speaks-core WS6a headline demonstration: an agent
pipeline written as a core YAML file (``tapestry.yaml``, using core's 9 node
types, no agents-only schema), loaded with
``pirn.yaml_loader.pipeline_loader.PipelineLoader.load_yaml`` exactly like any
other domain's pipeline, and checkable with the same validator every other
domain uses (``pirn.check.tapestry_validator.TapestryValidator``).

Run with:
    uv run python -m examples.agents_core_pipeline
"""

from __future__ import annotations

from pathlib import Path

from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.yaml_loader.pipeline_loader import PipelineLoader
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.types.messaging.agent_message import AgentMessage

from examples.agents_core_pipeline.example_echo_llm_provider import (
    ExampleEchoLLMProvider,
)


class AgentsCorePipeline:
    """Loads ``tapestry.yaml`` into a runnable ``Tapestry`` and runs it once."""

    @staticmethod
    def build_tapestry() -> Tapestry:
        """Return the loaded, unrun ``Tapestry`` for ``tapestry.yaml``.

        The LLM provider is registered under the reference label the YAML's
        ``source`` node names (``callable: llm``) via
        :meth:`~pirn_agents.builder.agent_references.AgentReferences.as_known_callables`
        — the mechanism that lets a core pipeline document name a caller-owned
        live object it cannot write into YAML text directly.
        """
        yaml_path = Path(__file__).parent / "tapestry.yaml"
        references = AgentReferences().register("llm", ExampleEchoLLMProvider("Paris"))
        return PipelineLoader.load_yaml(
            yaml_path.read_text(encoding="utf-8"),
            known_callables=references.as_known_callables(),
        )

    @classmethod
    async def main(cls) -> None:
        """Run the tapestry with one seed question; print the lineage and the answer."""
        tapestry = cls.build_tapestry()
        seed = (AgentMessage(role="user", content="What is the capital of France?"),)
        result = await tapestry.run(RunRequest(parameters={"seed_messages": seed}))
        for rec in result.lineage:
            print(f"  {rec.knot_id:<18} {rec.outcome}")
        print(result.outputs["agent"].data)
