"""``AgentBuilder`` — fluent, chainable facade that generates a knot graph.

``AgentBuilder`` collects the pieces of an agent — an LLM provider, tools, a
memory store, a pattern with its options, and a runtime input — through
chainable methods, then :meth:`build` generates an ordinary
:class:`~pirn.nodes.sub_tapestry.SubTapestry` with a stable, auto-derived knot
id. The generated graph is byte-for-byte equivalent to hand-wiring the
corresponding pattern class, so it shares the engine's caching and lineage
exactly.

Patterns need more than three kinds of part: a graph-RAG pipeline wants a
``graph_memory``, a self-query pipeline a ``store`` and an ``embedder``, a
debate a list of ``debaters``. :meth:`component` is the general slot — any
constructor parameter of the chosen pattern, supplied by name — and
:meth:`llm`, :meth:`tools` and :meth:`memory` are type-checked shorthand for the
three that recur most (PIR-730). :attr:`missing_components` reports what the
chosen pattern still needs, so a caller can ask rather than guess.

The builder is the **one authoring spine**: the fluent front end,
:class:`AgentSpec` its declarative serialisation in both directions
(:meth:`to_spec` out, :meth:`from_spec` in),
:class:`~pirn_agents.builder.agent_presets.AgentPresets` named entries into it,
and :class:`AgentPatternRegistry` the pattern table all of them consume
(PIR-732).

It is a *thin* convenience: it hides no capability. Every collected component is
readable back (``llm_provider``, ``tool_list``, ``memory_store``,
``components``, ``pattern_name``, ``options``), the target pattern class is
exposed via :attr:`pattern_class`, the derived id via :attr:`knot_id`, and a
declarative snapshot via :meth:`to_spec` — so advanced users can drop straight
to the knot-first API. See ``BUILDER.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.agent_knot_id_factory import AgentKnotIdFactory
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.toolset import Toolset

#: Component names with a dedicated, type-checked setter on the builder.
_SHORTHAND_COMPONENTS = frozenset({"llm", "memory", "tools"})


class AgentBuilder:
    """Chainable builder that generates a :class:`SubTapestry` agent graph."""

    @classmethod
    def from_spec(cls, spec: AgentSpec, *, references: AgentReferences) -> AgentBuilder:
        """Return a builder configured from a declarative :class:`AgentSpec`.

        The inverse of :meth:`to_spec`, and the step that makes the declarative
        surface able to *run* rather than only describe (PIR-732). A spec names
        its parts by reference label; ``references`` maps those labels to the
        live objects the caller owns.

        The returned builder still needs ``.input(...)``: a spec describes an
        agent's *shape*, not the runtime seed it is asked about, so one spec
        serves many inputs.

        Args:
            spec: The declarative description to configure from.
            references: Label-to-object table covering every label ``spec``
                names.

        Returns:
            A configured :class:`AgentBuilder`, ready for ``.input(...).build()``.

        Raises:
            TypeError: If ``spec``/``references`` have the wrong type, or a
                resolved object does not match the slot it fills.
            ValueError: If ``spec.pattern`` is not a known pattern.
            KeyError: If a label the spec names is not registered.
        """
        if not isinstance(spec, AgentSpec):
            raise TypeError(
                f"AgentBuilder.from_spec: spec must be an AgentSpec, got {type(spec).__name__}"
            )
        if not isinstance(references, AgentReferences):
            raise TypeError(
                f"AgentBuilder.from_spec: references must be an AgentReferences, "
                f"got {type(references).__name__}"
            )
        builder = cls()
        if spec.llm is not None:
            builder.llm(references.resolve(spec.llm))
        if spec.memory is not None:
            builder.memory(references.resolve(spec.memory))
        if spec.tools:
            builder.tools([references.resolve(label) for label in spec.tools])
        for name, label in spec.components.items():
            builder.component(name, references.resolve(label))
        return builder.pattern(spec.pattern, **spec.options)

    def __init__(self) -> None:
        """Start an empty builder with no components configured."""
        self._components: dict[str, Any] = {}
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
        self._components["llm"] = provider
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
        self._components["tools"] = tuple(self._tools)
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
        self._components["memory"] = store
        return self

    def component(self, name: str, value: Any) -> AgentBuilder:
        """Supply a pattern component by constructor-parameter name; return ``self``.

        The general form of :meth:`llm`/:meth:`memory`/:meth:`tools`, for the
        parts that vary by pattern — ``graph_memory``, ``embedder``, ``store``,
        ``pool``, ``specialists``, ``reviewers``, ``schema``, and so on. Ask the
        registry (or :attr:`missing_components`) which names a pattern needs.

        Args:
            name: A constructor parameter of the chosen pattern.
            value: The live object to bind to it.

        Raises:
            TypeError: If ``name`` is not a string.
            ValueError: If ``name`` is empty, or is one of ``llm``/``memory``/
                ``tools`` — those have type-checked setters and using them keeps
                the check.
        """
        if not isinstance(name, str):
            raise TypeError(
                f"AgentBuilder.component: name must be a str, got {type(name).__name__}"
            )
        if not name:
            raise ValueError("AgentBuilder.component: name must be a non-empty string")
        if name in _SHORTHAND_COMPONENTS:
            raise ValueError(
                f"AgentBuilder.component: use .{name}(...) to set {name!r} — it is type-checked"
            )
        self._components[name] = value
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
        # `descriptor` checks the name without importing the pattern's module.
        AgentPatternRegistry.descriptor(name)
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
        provider = self._components.get("llm")
        return provider if isinstance(provider, LLMProvider) else None

    @property
    def memory_store(self) -> MemoryStore | None:
        """The configured memory store, or ``None`` (escape-hatch accessor)."""
        store = self._components.get("memory")
        return store if isinstance(store, MemoryStore) else None

    @property
    def tool_list(self) -> tuple[Tool, ...]:
        """The configured tools in order (escape-hatch accessor)."""
        return tuple(self._tools)

    @property
    def components(self) -> Mapping[str, Any]:
        """A copy of every configured component, keyed by parameter name."""
        return dict(self._components)

    @property
    def missing_components(self) -> tuple[str, ...]:
        """Component names the chosen pattern requires that are not yet set.

        Empty means :meth:`build` will not fail for want of a component.

        Raises:
            ValueError: If no pattern has been selected yet.
        """
        if self._pattern is None:
            raise ValueError(
                "AgentBuilder.missing_components: no pattern selected; call .pattern(...)"
            )
        return tuple(
            name
            for name in AgentPatternRegistry.required_components(self._pattern)
            if name not in self._components and name not in self._options
        )

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
            llm=self._component_label("llm"),
            memory=self._component_label("memory"),
            tools=[tool.name for tool in self._tools],
            components=self._component_labels(),
            options=self._options,
            name=self._name,
        )

    def _component_label(self, name: str) -> str | None:
        """Return the reference label of one component, or ``None`` if unset."""
        value = self._components.get(name)
        return None if value is None else type(value).__name__

    def _component_labels(self) -> dict[str, str]:
        """Return reference labels for the components without a dedicated field.

        ``llm``/``memory``/``tools`` are carried by the id factory's own
        arguments, so restating them here would double-count them and change
        every previously derived id.
        """
        return {
            name: type(value).__name__
            for name, value in sorted(self._components.items())
            if name not in _SHORTHAND_COMPONENTS
        }

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
            llm=self._component_label("llm"),
            memory=self._component_label("memory"),
            tools=tuple(tool.name for tool in self._tools),
            components=self._component_labels(),
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
            ValueError: If no pattern is selected, no input is set, a component
                the pattern requires is missing, or a configured component or
                option is not a parameter of the chosen pattern.
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
            components=self._components,
            options=self._options,
        )
