"""``_ExtractionTool`` — a synthetic single-purpose tool for forced extraction.

An internal :class:`pirn_agents.tool.Tool` whose ``parameters_schema`` is the
target model's JSON schema. Forcing tool-choice to this one tool (S2) makes the
provider emit exactly the structured arguments the schema demands; the codec
decodes those arguments and they are validated in a single pass. ``invoke`` is
an identity echo — the tool is never executed, only declared — so a forced call
round-trips its arguments unchanged if a caller ever runs it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tool import Tool


class _ExtractionTool(Tool):
    """A schema-shaped tool used only to force a structured tool call."""

    def __init__(
        self, *, name: str, description: str, parameters_schema: Mapping[str, Any]
    ) -> None:
        """Bind the tool's identity and the schema its arguments must satisfy.

        Args:
            name: The tool name tool-choice is forced to.
            description: A short human-readable description declared to the LLM.
            parameters_schema: JSON Schema describing the extraction arguments.
        """
        self._name = name
        self._description = description
        self._parameters_schema: Mapping[str, Any] = dict(parameters_schema)

    @property
    def name(self) -> str:
        """Return the forced tool's name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the forced tool's description."""
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the target model's JSON schema as the tool's parameters."""
        return self._parameters_schema

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Echo ``arguments`` unchanged; the tool is declaration-only."""
        return dict(arguments)
