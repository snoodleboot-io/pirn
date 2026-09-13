"""``ToolCallValidator`` — validate a :class:`ToolCall` against its tool's declaration.

Validates the ToolCall's arguments against the capability's declared
``parameters`` before invocation and raises :exc:`ValueError` on a mismatch;
returns the validated :class:`ToolCall` unchanged on success.

The check is :meth:`ToolFactory.validate_arguments` — the declaration's
schema applied through core's ``JsonSchemaTypeBuilder`` adapters, the same
machinery a call knot's ``validate_io`` uses — rather than a hand-written
JSON-Schema subset (ADR agents-speaks-core, WS1).

Algorithm:
    1. Validate that ``tool_call`` is a :class:`ToolCall`.
    2. Build a name-keyed registry from the supplied ``tools`` sequence.
    3. Look up the tool by name; raise ``ValueError`` if not found.
    4. Ask the capability for every violation (missing required, unknown,
       mistyped); raise ``ValueError`` naming them when there are any.
    5. Return the original ``tool_call`` unchanged on success.


References:
    - JSON Schema specification: https://json-schema.org/draft/2020-12/json-schema-validation
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory


class ToolCallValidator(Knot):
    """Validate a ToolCall's arguments against the tool's declared parameters."""

    def __init__(
        self,
        *,
        tool_call: Knot | ToolCall,
        tools: Knot | Sequence[Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tool_call=tool_call, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        tool_call: ToolCall,
        tools: Sequence[ToolFactory],
        **_: Any,
    ) -> ToolCall:
        """Validate the ToolCall arguments against the registered tool's declaration.

        Args:
            tool_call: The ToolCall to validate before execution.
            tools: The capabilities to validate against.

        Returns:
            The original ToolCall unchanged when validation passes.

        Raises:
            TypeError: If tool_call is not a ToolCall or any element of tools is not a capability.
            ValueError: If the tool is not found or the arguments fail validation.
        """
        registry: dict[str, ToolFactory] = {}
        for index, tool in enumerate(tools):
            try:
                factory = ToolFactory.of(tool)
            except TypeError as exc:
                raise TypeError(
                    f"ToolCallValidator: tools[{index}] must be a Tool, got {type(tool).__name__}"
                ) from exc
            registry[factory.name] = factory

        factory = registry.get(tool_call.tool_name)
        if factory is None:
            raise ValueError(f"ToolCallValidator: unknown tool '{tool_call.tool_name}'")
        detail = factory.validate_arguments(tool_call.arguments)
        if detail:
            raise ValueError(
                f"ToolCallValidator: tool '{tool_call.tool_name}' rejected its arguments: {detail}"
            )
        return tool_call
