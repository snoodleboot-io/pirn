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
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


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
    options:
        Pattern-specific options (e.g. ``{"max_iterations": 6}``). Values are
        restricted to JSON primitives so the spec round-trips cleanly.
    """

    pattern: str
    llm: str | None = None
    memory: str | None = None
    tools: tuple[str, ...] = ()
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
        return ("pattern", "llm", "memory", "tools", "options")

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
            "options": dict(self.options),
        }

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the primitive audit form (identical to :meth:`to_dict`)."""
        return self.to_dict()
