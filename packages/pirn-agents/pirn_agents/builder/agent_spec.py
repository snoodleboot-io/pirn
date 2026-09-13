"""``AgentSpec`` — declarative, serialisable description of an agent graph.

An :class:`AgentSpec` is the config-driven counterpart of the fluent
:class:`~pirn_agents.builder.agent_builder.AgentBuilder`. It captures *what*
an agent is — its pattern, provider references, tool references, and pattern
options — in a form that round-trips losslessly to and from plain mappings
(and, via :class:`~pirn_agents.builder.agent_spec_loader.AgentSpecLoader`,
YAML/JSON). Because live provider objects (an LLM client, a memory store) are
not serialisable, the spec stores provider/tool *references* as plain strings;
resolving those references to concrete objects is the caller's responsibility.

The spec is a frozen, opaque value: it validates every field on construction
and rejects unknown keys on load, so a malformed config fails fast rather than
producing a half-wired agent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.yaml_loader.specs.knot_spec import KnotSpec
from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec
from pirn.yaml_loader.specs.yaml_parameter_spec import YamlParameterSpec

from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry


@dataclass(frozen=True)
class AgentSpec(PirnOpaqueValue):
    """Declarative description of an agent graph.

    Attributes
    ----------
    pattern:
        Name of the agentic pattern to generate (e.g. ``"react"``,
        ``"naive_rag"``). Required and non-empty.
    llm:
        Reference (label/name) of the LLM provider the agent uses, or
        ``None`` when unset.
    memory:
        Reference of the memory store the agent uses, or ``None``.
    tools:
        Ordered references of the tools the agent may call.
    components:
        References of the pattern's remaining components, keyed by constructor
        parameter name (``{"graph_memory": "Neo4jStore"}``). ``llm``, ``memory``
        and ``tools`` have their own fields and are not repeated here.
    options:
        Pattern-specific options (e.g. ``{"max_iterations": 6}``). Values are
        restricted to JSON primitives so the spec round-trips cleanly.
    """

    #: ``tags[0]`` on every reference node :meth:`to_pipeline_spec` emits,
    #: distinguishing it from the seed parameter node. ``ClassVar``s below are
    #: excluded from the dataclass's own fields (same convention as
    #: :class:`~pirn_agents.builder.pattern_descriptor.PatternDescriptor`).
    _reference_tag: ClassVar[str] = "agent-ref"
    #: ``tags[1]`` values identifying which :class:`AgentSpec` field a
    #: reference node round-trips into.
    _kind_llm: ClassVar[str] = "llm"
    _kind_memory: ClassVar[str] = "memory"
    _kind_tool: ClassVar[str] = "tool"
    _kind_component: ClassVar[str] = "component"

    pattern: str
    llm: str | None = None
    memory: str | None = None
    tools: tuple[str, ...] = ()
    components: Mapping[str, str] = field(default_factory=dict)
    options: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate field types and value domains.

        Raises
        ------
        TypeError
            If any field has the wrong type.
        ValueError
            If ``pattern`` is empty.
        """
        if not isinstance(self.pattern, str):
            raise TypeError(f"AgentSpec: pattern must be a str, got {type(self.pattern).__name__}")
        if not self.pattern:
            raise ValueError("AgentSpec: pattern must be a non-empty string")
        for label, value in (("llm", self.llm), ("memory", self.memory)):
            if value is not None and not isinstance(value, str):
                raise TypeError(
                    f"AgentSpec: {label} must be a str or None, got {type(value).__name__}"
                )
        if not isinstance(self.tools, tuple):
            raise TypeError(f"AgentSpec: tools must be a tuple, got {type(self.tools).__name__}")
        for index, name in enumerate(self.tools):
            if not isinstance(name, str):
                raise TypeError(
                    f"AgentSpec: tools[{index}] must be a str, got {type(name).__name__}"
                )
        if not isinstance(self.components, Mapping):
            raise TypeError(
                f"AgentSpec: components must be a mapping, got {type(self.components).__name__}"
            )
        component_refs: dict[str, str] = {}
        for key, reference in self.components.items():
            if not isinstance(key, str):
                raise TypeError(f"AgentSpec: component keys must be str, got {type(key).__name__}")
            if not isinstance(reference, str):
                raise TypeError(
                    f"AgentSpec: component {key!r} must be a str reference, "
                    f"got {type(reference).__name__}"
                )
            component_refs[key] = reference
        object.__setattr__(self, "components", component_refs)
        if not isinstance(self.options, Mapping):
            raise TypeError(
                f"AgentSpec: options must be a mapping, got {type(self.options).__name__}"
            )
        normalised: dict[str, str | int | float | bool] = {}
        for key, value in self.options.items():
            if not isinstance(key, str):
                raise TypeError(f"AgentSpec: option keys must be str, got {type(key).__name__}")
            # bool is a subclass of int; check it first so it is preserved as bool.
            if not isinstance(value, (bool, int, float, str)):
                raise TypeError(
                    f"AgentSpec: option {key!r} must be a str/int/float/bool, "
                    f"got {type(value).__name__}"
                )
            normalised[key] = value
        object.__setattr__(self, "options", normalised)

    @classmethod
    def allowed_fields(cls) -> tuple[str, ...]:
        """Return the field names a mapping may contain when loaded."""
        return ("pattern", "llm", "memory", "tools", "components", "options")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AgentSpec:
        """Build an :class:`AgentSpec` from a plain mapping, rejecting unknowns.

        Args:
            data: Mapping with keys drawn from :meth:`allowed_fields`.

        Returns:
            A validated :class:`AgentSpec`.

        Raises:
            TypeError: If ``data`` is not a mapping or a field has a bad type.
            ValueError: If ``data`` contains unknown keys or omits ``pattern``.
        """
        if not isinstance(data, Mapping):
            raise TypeError(
                f"AgentSpec.from_dict: data must be a mapping, got {type(data).__name__}"
            )
        allowed = set(cls.allowed_fields())
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                f"AgentSpec.from_dict: unknown field(s) {sorted(unknown)!r}; "
                f"allowed fields are {sorted(allowed)!r}"
            )
        if "pattern" not in data:
            raise ValueError("AgentSpec.from_dict: required field 'pattern' is missing")
        raw_tools = data.get("tools", ())
        if isinstance(raw_tools, str) or not isinstance(raw_tools, Sequence):
            raise TypeError(
                f"AgentSpec.from_dict: tools must be a sequence, got {type(raw_tools).__name__}"
            )
        return cls(
            pattern=data["pattern"],
            llm=data.get("llm"),
            memory=data.get("memory"),
            tools=tuple(raw_tools),
            # Passed through raw so __post_init__ reports a bad type by name.
            components=data.get("components", {}),
            options=dict(data.get("options", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serialisable mapping of this spec.

        ``tools`` is emitted as a list and ``options`` as a dict so the result
        round-trips through JSON/YAML back into an equal :class:`AgentSpec`.
        """
        return {
            "pattern": self.pattern,
            "llm": self.llm,
            "memory": self.memory,
            "tools": list(self.tools),
            "components": dict(self.components),
            "options": dict(self.options),
        }

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the primitive audit form (identical to :meth:`to_dict`)."""
        return self.to_dict()

    def to_pipeline_spec(self, *, node_id: str = "agent") -> PipelineSpec:
        """Return this spec as a core :class:`~pirn.yaml_loader.specs.pipeline_spec.PipelineSpec`.

        ``AgentSpec`` is a projection of core's own declarative vocabulary, not
        a parallel schema: the pattern becomes a ``knot`` node naming the
        pattern by its (now core-registry-resolvable — see
        :meth:`~pirn_agents.builder.agent_pattern_registry.AgentPatternRegistry.register_with_core_registry`)
        name as its ``callable``; ``options`` becomes that node's ``config``;
        the runtime seed becomes an unbound ``parameter`` node (an
        :class:`AgentSpec` describes an agent's *shape*, not the question it
        is asked — see ``AgentBuilder.from_spec``); and every reference
        (``llm``, ``memory``, each tool, each component) becomes its own
        ``parameter`` node, tagged so :meth:`from_pipeline_spec` can read the
        label back off it.

        ``llm``/``memory``/each named component are wired as real ``parents``
        of the knot node, so a caller who resolves those references (e.g. via
        :meth:`~pirn_agents.builder.agent_references.AgentReferences.as_known_callables`,
        wiring a ``source`` node in front of each in place of the bare
        parameter) gets a genuinely loadable pipeline. ``tools`` cannot be:
        each label is its own node (so every label survives the round trip
        distinctly), but the pattern's ``tools`` constructor parameter takes
        one sequence, not one parent per element — combining them needs a
        core ``aggregator`` node with a caller-supplied ``combine``, which
        this generic projection has no pattern-specific reason to assume. The
        tool reference nodes are present (for the round trip) but left
        unwired; a caller building a runnable graph from an
        :class:`AgentSpec` should go through
        ``AgentBuilder``/``AgentPatternRegistry`` instead, which already
        handles this via ``.tools(...)``.

        Args:
            node_id: Base id for the generated nodes. The knot node itself
                takes this id verbatim; every other node is scoped under it
                (``f"{node_id}:seed"``, ``f"{node_id}:ref:llm"``, ...) so two
                agents in the same document never collide.

        Returns:
            A :class:`PipelineSpec` — ``tapestry-check``-shaped, and losslessly
            convertible back via :meth:`from_pipeline_spec`.

        Raises:
            ValueError: If :attr:`pattern` is not a known pattern name.
        """
        AgentPatternRegistry.descriptor(self.pattern)  # eager validation; see AgentBuilder.pattern

        nodes: list[Any] = [YamlParameterSpec(id=f"{node_id}:seed", type="parameter", type_="Any")]
        parents: dict[str, str] = {}

        if self.llm is not None:
            ref_id = f"{node_id}:ref:llm"
            nodes.append(self._reference_node(ref_id, self._kind_llm, self.llm))
            parents["llm"] = ref_id
        if self.memory is not None:
            ref_id = f"{node_id}:ref:memory"
            nodes.append(self._reference_node(ref_id, self._kind_memory, self.memory))
            parents["memory"] = ref_id
        for index, label in enumerate(self.tools):
            nodes.append(
                self._reference_node(
                    f"{node_id}:ref:tool:{index}", self._kind_tool, label, extra=str(index)
                )
            )
        for name, label in self.components.items():
            ref_id = f"{node_id}:ref:component:{name}"
            nodes.append(self._reference_node(ref_id, self._kind_component, label, extra=name))
            parents[name] = ref_id

        nodes.append(
            KnotSpec(
                id=node_id,
                type="knot",
                callable=self.pattern,
                parents=parents,
                config=dict(self.options),
            )
        )
        return PipelineSpec(name=node_id, nodes=nodes)

    @staticmethod
    def _reference_node(
        node_id: str, kind: str, label: str, *, extra: str | None = None
    ) -> YamlParameterSpec:
        """Build one reference parameter node, tagged for :meth:`from_pipeline_spec`."""
        tags = [AgentSpec._reference_tag, kind]
        if extra is not None:
            tags.append(extra)
        return YamlParameterSpec(
            id=node_id, type="parameter", type_="Any", description=label, tags=tags
        )

    @classmethod
    def from_pipeline_spec(cls, pipeline_spec: PipelineSpec) -> AgentSpec:
        """Return the :class:`AgentSpec` a core pipeline document describes.

        The inverse of :meth:`to_pipeline_spec`: the single ``knot`` node's
        ``callable``/``config`` become ``pattern``/``options``, and every
        reference parameter node ``to_pipeline_spec`` tagged
        (``tags[0] == "agent-ref"``) becomes the corresponding
        ``llm``/``memory``/``tools``/``components`` entry, keyed by the
        label ``to_pipeline_spec`` wrote into its ``description``.

        Args:
            pipeline_spec: A document shaped like :meth:`to_pipeline_spec`'s
                output — one knot node describing the pattern, plus any number
                of tagged reference parameter nodes. A hand-authored core
                pipeline document following this same shape (see
                ``docs/guides/yaml-pipelines.md``, agents section) works too.

        Returns:
            The described :class:`AgentSpec`.

        Raises:
            ValueError: If ``pipeline_spec`` does not contain exactly one
                ``knot`` node, or tags a reference node with an unknown kind.
        """
        knot_nodes = [node for node in pipeline_spec.nodes if isinstance(node, KnotSpec)]
        if len(knot_nodes) != 1:
            raise ValueError(
                "AgentSpec.from_pipeline_spec: expected exactly one knot node describing "
                f"the agent's pattern, found {len(knot_nodes)}"
            )
        knot_node = knot_nodes[0]

        llm: str | None = None
        memory: str | None = None
        tools_by_index: dict[int, str] = {}
        components: dict[str, str] = {}
        for node in pipeline_spec.nodes:
            if not isinstance(node, YamlParameterSpec):
                continue
            if len(node.tags) < 2 or node.tags[0] != cls._reference_tag:
                continue
            kind = node.tags[1]
            label = node.description or ""
            if kind == cls._kind_llm:
                llm = label
            elif kind == cls._kind_memory:
                memory = label
            elif kind == cls._kind_tool:
                tools_by_index[int(node.tags[2])] = label
            elif kind == cls._kind_component:
                components[node.tags[2]] = label
            else:
                raise ValueError(
                    f"AgentSpec.from_pipeline_spec: node {node.id!r} tags an unknown "
                    f"reference kind {kind!r}"
                )

        return cls(
            pattern=knot_node.callable,
            llm=llm,
            memory=memory,
            tools=tuple(tools_by_index[index] for index in sorted(tools_by_index)),
            components=components,
            options=dict(knot_node.config),
        )
