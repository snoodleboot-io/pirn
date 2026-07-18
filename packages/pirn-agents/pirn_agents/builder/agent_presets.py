"""``AgentPresets`` — curated, provider-neutral agent recipes.

Each preset is a one-call recipe that wires a sensible default pattern and
tool set through the *public* :class:`~pirn_agents.builder.agent.Agent` builder
API — nothing a caller could not assemble by hand. Presets are deliberately
provider-neutral: the LLM provider (and memory store, where relevant) is always
supplied by the caller, and every default tool set can be overridden, so no
preset privileges a specific vendor.

Like :meth:`AgentBuilder.build`, each preset must be called inside an active
``Tapestry`` context so the generated :class:`SubTapestry` registers into the
caller's graph.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.agent import Agent
from pirn_agents.memory_store import MemoryStore
from pirn_agents.tool import Tool
from pirn_agents.tools.bundles import (
    calculator_toolset,
    filesystem_toolset,
    web_toolset,
)
from pirn_agents.toolset import Toolset


class AgentPresets:
    """Curated recipes that build ready :class:`SubTapestry` agents."""

    @classmethod
    def research(
        cls,
        *,
        llm: LLMProvider,
        input: object,
        tools: Toolset | Sequence[Tool] | None = None,
        max_iterations: int = 6,
        name: str | None = None,
    ) -> SubTapestry:
        """Build a ReAct research agent with web fetch/read tools by default.

        Args:
            llm: Any :class:`LLMProvider` (caller-supplied; no vendor assumed).
            input: The research question — a string or a message sequence.
            tools: Override tool set; defaults to a backend-free web toolset
                (HTTP fetch + HTML-to-text). Pass a search-backed
                :func:`web_toolset` or your own tools to extend it.
            max_iterations: ReAct iteration cap.
            name: Optional explicit knot-id name.

        Returns:
            The generated :class:`SubTapestry`.
        """
        selected = web_toolset() if tools is None else tools
        builder = (
            Agent.builder()
            .llm(llm)
            .tools(selected)
            .pattern("react", max_iterations=max_iterations)
            .input(input)
        )
        if name is not None:
            builder = builder.name(name)
        return builder.build()

    @classmethod
    def rag_chat(
        cls,
        *,
        llm: LLMProvider,
        memory: MemoryStore,
        input: str,
        top_k: int = 5,
        name: str | None = None,
    ) -> SubTapestry:
        """Build a naive-RAG chatbot over a caller-supplied memory store.

        Args:
            llm: Any :class:`LLMProvider` (caller-supplied; no vendor assumed).
            memory: The :class:`MemoryStore` retrieved context comes from.
            input: The user query string.
            top_k: Number of memories to retrieve.
            name: Optional explicit knot-id name.

        Returns:
            The generated :class:`SubTapestry`.
        """
        builder = (
            Agent.builder().llm(llm).memory(memory).pattern("naive_rag", top_k=top_k).input(input)
        )
        if name is not None:
            builder = builder.name(name)
        return builder.build()

    @classmethod
    def coding(
        cls,
        *,
        llm: LLMProvider,
        input: object,
        root: str,
        tools: Toolset | Sequence[Tool] | None = None,
        max_iterations: int = 8,
        name: str | None = None,
    ) -> SubTapestry:
        """Build a ReAct coding agent with filesystem + calculator tools.

        Args:
            llm: Any :class:`LLMProvider` (caller-supplied; no vendor assumed).
            input: The coding task — a string or a message sequence.
            root: Directory the default filesystem tools are confined to.
            tools: Override tool set; defaults to a filesystem toolset scoped to
                ``root`` plus a calculator.
            max_iterations: ReAct iteration cap.
            name: Optional explicit knot-id name.

        Returns:
            The generated :class:`SubTapestry`.
        """
        if tools is None:
            selected: Toolset | Sequence[Tool] = filesystem_toolset(root=root).merge(
                calculator_toolset()
            )
        else:
            selected = tools
        builder = (
            Agent.builder()
            .llm(llm)
            .tools(selected)
            .pattern("react", max_iterations=max_iterations)
            .input(input)
        )
        if name is not None:
            builder = builder.name(name)
        return builder.build()
