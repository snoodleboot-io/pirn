"""``AgentPresets`` — curated, provider-neutral agent recipes.

Each preset is a one-call recipe that wires a sensible default pattern and
tool set through the *public* :class:`~pirn_agents.builder.agent.Agent` builder
API — nothing a caller could not assemble by hand. Presets are deliberately
provider-neutral: the LLM provider (and memory store, where relevant) is always
supplied by the caller, and every default tool set can be overridden, so no
preset privileges a specific vendor.

Presets are **named entries into the one spine**, not a fourth authoring
surface (PIR-732). :meth:`builder_for` hands back the very
:class:`~pirn_agents.builder.agent_builder.AgentBuilder` a preset would build
from, so a recipe can be inspected, adjusted, or serialised with ``.to_spec()``
before it is committed to — and the named methods below are that same call
followed by ``.build()``, with no second copy of the defaults to drift.

Like :meth:`AgentBuilder.build`, each preset must be called inside an active
``Tapestry`` context so the generated :class:`SubTapestry` registers into the
caller's graph. :meth:`builder_for` needs no context; only ``.build()`` does.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.tools.bundles import (
    calculator_toolset,
    filesystem_toolset,
    web_toolset,
)
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.toolset import Toolset


class AgentPresets:
    """Curated recipes that build ready :class:`SubTapestry` agents."""

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return the available preset names, sorted."""
        return ("coding", "rag_chat", "research")

    @classmethod
    def builder_for(cls, preset: str, **kwargs: Any) -> AgentBuilder:
        """Return the configured builder ``preset`` uses, without building it.

        The recipe as an inspectable object rather than a finished graph: read
        ``.to_spec()`` to see it as data, ``.knot_id`` to see the id it will
        take, or keep chaining to adjust it. ``preset(**kwargs)`` is exactly
        this call followed by ``.build()``.

        Args:
            preset: One of :meth:`names`.
            **kwargs: The keyword arguments of the matching preset method.

        Raises:
            ValueError: If ``preset`` is not a known preset name.
            TypeError: If ``kwargs`` do not match that preset's signature.
        """
        recipes = {
            "coding": cls._coding_builder,
            "rag_chat": cls._rag_chat_builder,
            "research": cls._research_builder,
        }
        recipe = recipes.get(preset)
        if recipe is None:
            raise ValueError(
                f"AgentPresets.builder_for: unknown preset {preset!r}; "
                f"known presets are {list(cls.names())!r}"
            )
        return recipe(**kwargs)

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
        return cls._research_builder(
            llm=llm, input=input, tools=tools, max_iterations=max_iterations, name=name
        ).build()

    @classmethod
    def _research_builder(
        cls,
        *,
        llm: LLMProvider,
        input: object,
        tools: Toolset | Sequence[Tool] | None = None,
        max_iterations: int = 6,
        name: str | None = None,
    ) -> AgentBuilder:
        """Configure the research recipe; see :meth:`research` for the arguments."""
        selected = web_toolset() if tools is None else tools
        builder = (
            Agent.builder()
            .llm(llm)
            .tools(selected)
            .pattern("react", max_iterations=max_iterations)
            .input(input)
        )
        return builder if name is None else builder.name(name)

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
        return cls._rag_chat_builder(
            llm=llm, memory=memory, input=input, top_k=top_k, name=name
        ).build()

    @classmethod
    def _rag_chat_builder(
        cls,
        *,
        llm: LLMProvider,
        memory: MemoryStore,
        input: str,
        top_k: int = 5,
        name: str | None = None,
    ) -> AgentBuilder:
        """Configure the rag_chat recipe; see :meth:`rag_chat` for the arguments."""
        builder = (
            Agent.builder().llm(llm).memory(memory).pattern("naive_rag", top_k=top_k).input(input)
        )
        return builder if name is None else builder.name(name)

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
        return cls._coding_builder(
            llm=llm,
            input=input,
            root=root,
            tools=tools,
            max_iterations=max_iterations,
            name=name,
        ).build()

    @classmethod
    def _coding_builder(
        cls,
        *,
        llm: LLMProvider,
        input: object,
        root: str,
        tools: Toolset | Sequence[Tool] | None = None,
        max_iterations: int = 8,
        name: str | None = None,
    ) -> AgentBuilder:
        """Configure the coding recipe; see :meth:`coding` for the arguments."""
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
        return builder if name is None else builder.name(name)
