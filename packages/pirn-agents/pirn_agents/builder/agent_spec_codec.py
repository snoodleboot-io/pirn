"""``AgentSpecCodec`` — round-trips an :class:`AgentBuilder` through :class:`AgentSpec`.

Extracted from :class:`~pirn_agents.builder.agent_builder.AgentBuilder` (PIR-856,
SRP) to separate the builder's fluent, chainable configuration surface from the
declarative serialisation concern: turning a live builder into a
JSON/YAML-friendly :class:`~pirn_agents.builder.agent_spec.AgentSpec` snapshot
(:meth:`to_spec`) and reconstructing a builder from one plus a live-object
:class:`~pirn_agents.builder.agent_references.AgentReferences` table
(:meth:`from_spec`).

Both directions are intimate collaborators of ``AgentBuilder`` rather than a
general-purpose API: :meth:`to_spec` reads the builder's private component
state directly (its own escape-hatch properties are keyed differently — by
component *value*, not reference *label*), and :meth:`from_spec` drives the
builder purely through its public chainable methods. The circular type
reference (the codec constructs and reads an ``AgentBuilder``; the builder
delegates to the codec) is broken by only importing
:class:`~pirn_agents.builder.agent_builder.AgentBuilder` for type-checking —
``from_spec`` receives the builder class as a parameter (``builder_cls``)
instead of importing it at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.builder.agent_spec import AgentSpec

if TYPE_CHECKING:
    from pirn_agents.builder.agent_builder import AgentBuilder


class AgentSpecCodec:
    """Converts between a live :class:`AgentBuilder` and a declarative :class:`AgentSpec`."""

    @staticmethod
    def from_spec(
        builder_cls: type[AgentBuilder], spec: AgentSpec, *, references: AgentReferences
    ) -> AgentBuilder:
        """Return a builder configured from a declarative :class:`AgentSpec`.

        The inverse of :meth:`to_spec`, and the step that makes the declarative
        surface able to *run* rather than only describe (PIR-732). A spec names
        its parts by reference label; ``references`` maps those labels to the
        live objects the caller owns.

        The returned builder still needs ``.input(...)``: a spec describes an
        agent's *shape*, not the runtime seed it is asked about, so one spec
        serves many inputs.

        Args:
            builder_cls: The :class:`AgentBuilder` class to instantiate
                (passed in, rather than imported here, to avoid a runtime
                import cycle between the builder and this codec).
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
        builder = builder_cls()
        if spec.llm is not None:
            builder.llm(references.resolve(spec.llm))
        if spec.memory is not None:
            builder.memory(references.resolve(spec.memory))
        if spec.tools:
            builder.tools([references.resolve(label) for label in spec.tools])
        for name, label in spec.components.items():
            builder.component(name, references.resolve(label))
        return builder.pattern(spec.pattern, **spec.options)

    @staticmethod
    def to_spec(builder: AgentBuilder) -> AgentSpec:
        """Return a declarative :class:`AgentSpec` snapshot of ``builder``.

        Live provider/tool objects are represented by their reference labels
        (provider class names, tool names) so the snapshot is serialisable.

        Raises:
            ValueError: If ``builder`` has no pattern selected yet.
        """
        pattern = builder.pattern_name
        if pattern is None:
            raise ValueError("AgentBuilder.to_spec: no pattern selected; call .pattern(...)")
        return AgentSpec(
            pattern=pattern,
            llm=builder._component_label("llm"),
            memory=builder._component_label("memory"),
            tools=tuple(tool.name for tool in builder.tool_list),
            components=builder._component_labels(),
            options=dict(builder.options),
        )
