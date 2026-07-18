"""``AgentPatternRegistry`` — map pattern names to knot-graph constructors.

This registry is the single place that knows how a named pattern
(``"react"``, ``"naive_rag"``) maps onto a concrete
:class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass and how the builder's
collected components (llm, tools, memory, input, options) are wired into that
class's constructor. Keeping this knowledge here keeps
:class:`~pirn_agents.builder.agent_builder.AgentBuilder` thin, and — crucially —
the classes it constructs (:class:`~pirn_agents.specializations.react.react_loop.ReActLoop`,
:class:`~pirn_agents.specializations.rag.naive_rag_pipeline.NaiveRAGPipeline`)
remain directly usable by hand; the registry adds no capability of its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRAGPipeline
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.tool import Tool
from pirn_agents.types.agent_message import AgentMessage


class AgentPatternRegistry:
    """Resolves pattern names to :class:`SubTapestry` subclasses and builds them."""

    @classmethod
    def _pattern_classes(cls) -> dict[str, type[SubTapestry]]:
        """Return the name-to-class table, including aliases."""
        return {
            "react": ReActLoop,
            "naive_rag": NaiveRAGPipeline,
            "rag": NaiveRAGPipeline,
        }

    @classmethod
    def pattern_names(cls) -> tuple[str, ...]:
        """Return the sorted, supported pattern names (including aliases)."""
        return tuple(sorted(cls._pattern_classes()))

    @classmethod
    def pattern_class(cls, pattern: str) -> type[SubTapestry]:
        """Return the :class:`SubTapestry` subclass a pattern name maps to.

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        table = cls._pattern_classes()
        knot_class = table.get(pattern)
        if knot_class is None:
            raise ValueError(
                f"AgentPatternRegistry: unknown pattern {pattern!r}; "
                f"known patterns are {list(cls.pattern_names())!r}"
            )
        return knot_class

    @classmethod
    def build(
        cls,
        pattern: str,
        *,
        knot_id: str,
        input_value: Any,
        llm: LLMProvider | None,
        tools: Sequence[Tool] = (),
        memory: MemoryStore | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> SubTapestry:
        """Construct the pattern's :class:`SubTapestry` from resolved components.

        Args:
            pattern: The agentic pattern name (or alias).
            knot_id: Stable id for the generated top-level knot.
            input_value: The runtime seed — a query string or messages for
                ``react``; a query string for ``naive_rag``.
            llm: The LLM provider (required by every current pattern).
            tools: Tools available to the agent (used by ``react``).
            memory: The memory store (required by ``naive_rag``).
            options: Pattern options (``max_iterations`` for ``react``,
                ``top_k`` for ``naive_rag``).

        Returns:
            A constructed :class:`SubTapestry` equivalent to hand-wiring the
            corresponding pattern class.

        Raises:
            ValueError: If ``pattern`` is unknown or a required component is
                missing.
            TypeError: If a component has the wrong type.
        """
        knot_class = cls.pattern_class(pattern)
        opts = dict(options or {})
        config = KnotConfig(id=knot_id)
        if knot_class is ReActLoop:
            return cls._build_react(config, input_value, llm, tools, opts)
        return cls._build_naive_rag(config, input_value, llm, memory, opts)

    @classmethod
    def _build_react(
        cls,
        config: KnotConfig,
        input_value: Any,
        llm: LLMProvider | None,
        tools: Sequence[Tool],
        options: Mapping[str, Any],
    ) -> SubTapestry:
        if llm is None:
            raise ValueError("AgentPatternRegistry: pattern 'react' requires an llm")
        messages = cls._normalise_messages(input_value)
        max_iterations = int(options.get("max_iterations", 10))
        return ReActLoop(
            messages=messages,
            llm=llm,
            tools=tuple(tools),
            max_iterations=max_iterations,
            _config=config,
        )

    @classmethod
    def _build_naive_rag(
        cls,
        config: KnotConfig,
        input_value: Any,
        llm: LLMProvider | None,
        memory: MemoryStore | None,
        options: Mapping[str, Any],
    ) -> SubTapestry:
        if llm is None:
            raise ValueError("AgentPatternRegistry: pattern 'naive_rag' requires an llm")
        if memory is None:
            raise ValueError("AgentPatternRegistry: pattern 'naive_rag' requires a memory store")
        if not isinstance(input_value, str):
            raise TypeError(
                f"AgentPatternRegistry: pattern 'naive_rag' requires a str query input, "
                f"got {type(input_value).__name__}"
            )
        top_k = int(options.get("top_k", 5))
        return NaiveRAGPipeline(
            query=input_value,
            memory=memory,
            llm=llm,
            top_k=top_k,
            _config=config,
        )

    @classmethod
    def _normalise_messages(cls, input_value: Any) -> tuple[AgentMessage, ...]:
        """Coerce a builder input into a tuple of :class:`AgentMessage`.

        A bare string becomes a single ``user`` message; a sequence of
        :class:`AgentMessage` is passed through as a tuple.

        Raises:
            TypeError: If ``input_value`` is neither a string nor a sequence of
                :class:`AgentMessage`.
        """
        if isinstance(input_value, str):
            return (AgentMessage(role="user", content=input_value),)
        if isinstance(input_value, AgentMessage):
            return (input_value,)
        if isinstance(input_value, Sequence):
            messages = tuple(input_value)
            for index, message in enumerate(messages):
                if not isinstance(message, AgentMessage):
                    raise TypeError(
                        f"AgentPatternRegistry: input[{index}] must be an AgentMessage, "
                        f"got {type(message).__name__}"
                    )
            return messages
        raise TypeError(
            "AgentPatternRegistry: 'react' input must be a str or a sequence of "
            f"AgentMessage, got {type(input_value).__name__}"
        )
