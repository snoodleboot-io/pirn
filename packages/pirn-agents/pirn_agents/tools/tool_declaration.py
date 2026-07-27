"""``ToolDeclaration`` — the provider-neutral envelope a tool is declared with.

Every provider is told about a tool with the same three facts: a ``name``, a
``description``, and a ``parameters`` JSON Schema. Only the *framing* of those
three differs per provider — chat-completions nests them under
``function``, the Messages API renames ``parameters`` to ``input_schema`` —
and that framing is the job of a
:class:`pirn_agents.llm.provider_adapter.ProviderAdapter`.

Before this class existed the neutral triple was re-spelled as bare string
keys in two places (``Toolset.schema()`` and ``FunctionTool.describe()``) and
hard-read by every adapter, with nothing tying the producers to each other.
:class:`ToolDeclaration` names that contract once and gives in-process callers
typed attribute access; :meth:`to_payload` remains the single place the wire
dict is built.

**The envelope is modelled; the JSON Schema inside it is not.** ``parameters``
stays a plain :class:`~collections.abc.Mapping` that is copied through
verbatim. JSON Schema is open, recursive and vendor-extensible — MCP servers
hand us arbitrary schemas at runtime — and the wire shape has load-bearing
details a re-serialising model would silently destroy (``required`` is omitted
rather than emitted empty; ``title`` is popped; ``None`` values survive). This
class must never grow a typed view of that payload.

Like the rest of the tools package, the value is opaque to pydantic (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`), so the engine does not
descend into a vendor schema at knot IO boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ToolDeclaration(PirnOpaqueValue):
    """One tool's provider-neutral ``{name, description, parameters}`` triple.

    Attributes
    ----------
    name:
        The stable identifier a provider addresses the tool by.
    description:
        Human-readable text shown to the model when it chooses a tool.
    parameters:
        The tool's JSON Schema ``parameters`` object, carried opaquely.
    """

    name: str
    description: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("ToolDeclaration: name must be a non-empty str")
        if not isinstance(self.description, str):
            raise TypeError(
                f"ToolDeclaration: description must be a str, got {type(self.description).__name__}"
            )
        if not isinstance(self.parameters, Mapping):
            raise TypeError(
                f"ToolDeclaration: parameters must be a Mapping, "
                f"got {type(self.parameters).__name__}"
            )

    def to_payload(self) -> dict[str, Any]:
        """Return the neutral wire dict a :class:`ProviderAdapter` consumes.

        Key order and key set are part of the contract: adapters index
        ``name`` / ``description`` / ``parameters`` directly. ``parameters``
        is shallow-copied into a plain ``dict`` so callers cannot mutate the
        owning tool's schema, and is otherwise passed through untouched.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> ToolDeclaration:
        """Rebuild a declaration from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ToolDeclaration.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            name=str(payload["name"]),
            description=str(payload["description"]),
            parameters=payload["parameters"],
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
