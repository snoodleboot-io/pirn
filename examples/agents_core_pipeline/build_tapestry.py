"""Factory: load ``tapestry.yaml`` into a runnable ``Tapestry``.

Shaped as ``MODULE:FUNCTION`` — ``build_tapestry`` — so ``tapestry-check`` can
load and statically validate it directly, exactly as it would any other
pipeline (see ``packages/pirn-core/tests/unit/test_check.py``'s own
``build_valid``/``build_empty`` factories for the same shape):

    uv run tapestry-check examples.agents_core_pipeline.build_tapestry:build_tapestry

This is the ADR agents-speaks-core WS6a headline demonstration: an agent
pipeline written as a core YAML file (``tapestry.yaml``, using core's 9 node
types, no agents-only schema), loaded with
``pirn.yaml_loader.pipeline_loader.PipelineLoader.load_yaml`` exactly like any other
domain's pipeline, and checkable with the same tool every other domain uses.

``ExampleEchoLLMProvider`` lives here rather than in its own file (unlike
every other class in this package) to keep this example a single,
copy-pasteable file, matching ``examples/content_moderation/knots.py``'s own
looser, script-shaped convention for example code (as opposed to library
code, which the one-class-per-file rule governs).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from pirn.tapestry import Tapestry
from pirn.yaml_loader.pipeline_loader import PipelineLoader
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta

YAML_PATH = Path(__file__).parent / "tapestry.yaml"


class ExampleEchoLLMProvider(LLMProvider):
    """Always answers ``"Final Answer: <reply>"`` — deterministic, offline.

    Exists only to satisfy ``react``'s required ``llm`` component without an
    API key or network access — not a template for a real provider (see
    ``pirn_agents.llm`` for the Anthropic/OpenAI-compatible ones).
    """

    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        return {"role": "assistant", "content": f"Final Answer: {self._reply}"}

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        async def _one_chunk() -> AsyncIterator[StreamDelta]:
            yield StreamDelta(content=f"Final Answer: {self._reply}")

        return _one_chunk()

    async def close(self) -> None:
        return None


def build_tapestry() -> Tapestry:
    """Return the loaded, unrun ``Tapestry`` for ``tapestry.yaml``.

    The LLM provider is registered under the reference label the YAML's
    ``source`` node names (``callable: llm``) via
    :meth:`~pirn_agents.builder.agent_references.AgentReferences.as_known_callables`
    — the mechanism that lets a core pipeline document name a caller-owned
    live object it cannot write into YAML text directly.
    """
    references = AgentReferences().register("llm", ExampleEchoLLMProvider("Paris"))
    return PipelineLoader.load_yaml(
        YAML_PATH.read_text(encoding="utf-8"),
        known_callables=references.as_known_callables(),
    )
