"""``_ExtractionTool`` — a synthetic single-purpose tool for forced extraction.

An internal tool capability whose declared ``parameters`` are the target
model's JSON schema. Forcing tool-choice to this one tool (S2) makes the
provider emit exactly the structured arguments the schema demands; the codec
decodes those arguments and they are validated in a single pass. The knot's
``process`` is an identity echo — the tool is declared, never executed — so a
forced call round-trips its arguments unchanged if a caller ever runs it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.tool_factory import ToolFactory


class _ExtractionTool(ToolFactory):
    """A schema-shaped tool capability used only to force a structured tool call."""

    def __init__(
        self, *, name: str, description: str, parameters_schema: Mapping[str, Any]
    ) -> None:
        """Bind the tool's identity and the schema its arguments must satisfy.

        Args:
            name: The tool name tool-choice is forced to.
            description: A short human-readable description declared to the LLM.
            parameters_schema: JSON Schema describing the extraction arguments.
        """
        knot_class = ToolFactory.schema_declared_class(
            f"ExtractionTool_{name}",
            {
                "type": "object",
                "properties": {"arguments": {"type": "object"}},
                "required": ["arguments"],
            },
            self._echo,
            description=description,
            tool_name=name,
        )
        super().__init__(
            knot_class, name=name, description=description, parameters=dict(parameters_schema)
        )
        self._packs_arguments = True

    @staticmethod
    async def _echo(**kwargs: Any) -> Any:
        """Echo the packed ``arguments`` unchanged; the tool is declaration-only."""
        return dict(kwargs.get("arguments", {}))
