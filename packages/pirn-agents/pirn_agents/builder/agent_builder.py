"""``AgentBuilder`` — fluent, chainable facade that generates a knot graph.

``AgentBuilder`` collects the pieces of an agent — an LLM provider, tools, a
memory store, a pattern with its options, and a runtime input — through
chainable methods, then :meth:`build` generates an ordinary
:class:`~pirn.nodes.sub_tapestry.SubTapestry` with a stable, auto-derived knot
id. The generated graph is byte-for-byte equivalent to hand-wiring the
corresponding pattern class, so it shares the engine's caching and lineage
exactly.

The builder is a *thin* convenience: it hides no capability. Every collected
component is readable back (``llm_provider``, ``tool_list``, ``memory_store``,
``pattern_name``, ``options``), the target pattern class is exposed via
:attr:`pattern_class`, the derived id via :attr:`knot_id`, and a declarative
snapshot via :meth:`to_spec` — so advanced users can drop straight to the
knot-first API. See ``BUILDER.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.agent_knot_id_factory import AgentKnotIdFactory
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.memory_store import MemoryStore
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset


class AgentBuilder:
    """Chainable builder that generates a :class:`SubTapestry` agent graph."""

    def __init__(self) -> None:
        """Start an empty builder with no components configured."""
        self._llm: LLMProvider | None = None
        self._memory: MemoryStore | None = None
        self._tools: list[Tool] = []
        self._pattern: str | None = None
        self._options: dict[str, Any] = {}
        self._input: Any = None
        self._name: str | None = None

    def llm(self, provider: LLMProvider) -> AgentBuilder:
        """Set the LLM provider and return ``self`` for chaining.

        Raises:
            TypeError: If ``provider`` is not an :class:`LLMProvider`.
        """
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                f"AgentBuilder.llm: provider must be an LLMProvider, got {type(provider).__name__}"
            )
        self._llm = provider
        return self

    def tools(self, tools: Toolset | Sequence[Tool]) -> AgentBuilder:
        """Append tools (a :class:`Toolset` or sequence) and return ``self``.

        Raises:
            TypeError: If ``tools`` is not iterable of :class:`Tool`, or any
                element is not a :class:`Tool`.
        """
        if isinstance(tools, Toolset):
            candidates: list[Tool] = list(tools)
        elif isinstance(tools, Sequence) and not isinstance(tools, (str, bytes)):
            candidates = list(tools)
        else:
            raise TypeError(
                f"AgentBuilder.tools: expected a Toolset or sequence of Tool, "
                f"got {type(tools).__name__}"
            )
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"AgentBuilder.tools: tools[{index}] must be a Tool, got {type(candidate).__name__}"
                )
        self._tools.extend(candidates)
        return self

    def memory(self, store: MemoryStore) -> AgentBuilder:
        """Set the memory store and return ``self`` for chaining.

        Raises:
            TypeError: If ``store`` is not a :class:`MemoryStore`.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"AgentBuilder.memory: store must be a MemoryStore, got {type(store).__name__}"
            )
        self._memory = store
        return self

    def pattern(self, name: str, **options: Any) -> AgentBuilder:
        """Select the agentic pattern and its options; return ``self``.

        Args:
            name: A pattern name known to :class:`AgentPatternRegistry`.
            **options: Pattern options (e.g. ``max_iterations=6``, ``top_k=8``).

        Raises:
            TypeError: If ``name`` is not a string.
            ValueError: If ``name`` is not a known pattern.
        """
        if not isinstance(name, str):
            raise TypeError(f"AgentBuilder.pattern: name must be a str, got {type(name).__name__}")
        # Validate eagerly so a typo fails at configuration time, not build time.
        AgentPatternRegistry.pattern_class(name)
        self._pattern = name
        self._options = dict(options)
        return self

    def input(self, value: Any) -> AgentBuilder:
        """Set the runtime seed (query string or messages); return ``self``."""
        self._input = value
        return self

    def name(self, name: str) -> AgentBuilder:
        """Pin an explicit knot id name (skips digest derivation); return ``self``.

        Raises:
            TypeError: If ``name`` is not a string.
        """
        if not isinstance(name, str):
            raise TypeError(f"AgentBuilder.name: name must be a str, got {type(name).__name__}")
        self._name = name
        return self

    @property
    def llm_provider(self) -> LLMProvider | None:
        """The configured LLM provider, or ``None`` (escape-hatch accessor)."""
        return self._llm

    @property
    def memory_store(self) -> MemoryStore | None:
        """The configured memory store, or ``None`` (escape-hatch accessor)."""
        return self._memory

    @property
    def tool_list(self) -> tuple[Tool, ...]:
        """The configured tools in order (escape-hatch accessor)."""
        return tuple(self._tools)

    @property
    def pattern_name(self) -> str | None:
        """The selected pattern name, or ``None`` (escape-hatch accessor)."""
        return self._pattern

    @property
    def options(self) -> Mapping[str, Any]:
        """A copy of the configured pattern options (escape-hatch accessor)."""
        return dict(self._options)

    @property
    def input_value(self) -> Any:
        """The configured runtime seed (escape-hatch accessor)."""
        return self._input

    @property
    def pattern_class(self) -> type[SubTapestry]:
        """The :class:`SubTapestry` subclass ``build`` will construct.

        Raises:
            ValueError: If no pattern has been selected yet.
        """
        if self._pattern is None:
            raise ValueError("AgentBuilder.pattern_class: no pattern selected; call .pattern(...)")
        return AgentPatternRegistry.pattern_class(self._pattern)

    @property
    def knot_id(self) -> str:
        """The stable knot id ``build`` will assign to the generated graph.

        Raises:
            ValueError: If no pattern has been selected yet.
        """
        if self._pattern is None:
            raise ValueError("AgentBuilder.knot_id: no pattern selected; call .pattern(...)")
        return AgentKnotIdFactory.derive(
            pattern=self._pattern,
            llm=None if self._llm is None else type(self._llm).__name__,
            memory=None if self._memory is None else type(self._memory).__name__,
            tools=[tool.name for tool in self._tools],
            options=self._options,
            name=self._name,
        )

    def to_spec(self) -> AgentSpec:
        """Return a declarative :class:`AgentSpec` snapshot of this builder.

        Live provider/tool objects are represented by their reference labels
        (provider class names, tool names) so the snapshot is serialisable.

        Raises:
            ValueError: If no pattern has been selected yet.
        """
        if self._pattern is None:
            raise ValueError("AgentBuilder.to_spec: no pattern selected; call .pattern(...)")
        return AgentSpec(
            pattern=self._pattern,
            llm=None if self._llm is None else type(self._llm).__name__,
            memory=None if self._memory is None else type(self._memory).__name__,
            tools=tuple(tool.name for tool in self._tools),
            options=dict(self._options),
        )

    def build(self) -> SubTapestry:
        """Generate the agent's :class:`SubTapestry` with a stable knot id.

        Must be called inside an active ``Tapestry`` context so the generated
        knot registers into the caller's graph, exactly like a hand-wired knot.

        Returns:
            The generated :class:`SubTapestry` (also reachable, unbuilt, via
            :attr:`pattern_class` for the fully hand-wired equivalent).

        Raises:
            ValueError: If no pattern is selected, or a required component
                (llm/memory/input) is missing.
            TypeError: If the runtime input has a type the pattern cannot use.
        """
        if self._pattern is None:
            raise ValueError(
                "AgentBuilder.build: no pattern selected; call .pattern(...) before build()"
            )
        if self._input is None:
            raise ValueError("AgentBuilder.build: no input set; call .input(...) before build()")
        return AgentPatternRegistry.build(
            self._pattern,
            knot_id=self.knot_id,
            input_value=self._input,
            llm=self._llm,
            tools=tuple(self._tools),
            memory=self._memory,
            options=self._options,
        )
