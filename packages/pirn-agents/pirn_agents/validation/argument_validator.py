"""``ArgumentValidator`` — deprecated (one cycle); the knot's adapters validate arguments now.

Before the ADR "agents speaks core" (WS1) this class implemented a small
JSON-Schema subset by hand to check a call's arguments before a tool ran.
A tool call is a knot now: its arguments are its inputs, validated at
construction through the same ``TypeAdapter``\\s ``validate_io`` uses (core's
``JsonSchemaTypeBuilder`` for a declared schema), and
:meth:`ToolFactory.validate_arguments` reports every violation as the
``{argument: reason}`` mapping this class used to produce.  :meth:`validate`
forwards there and warns; the class will be removed next cycle.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class ArgumentValidator(PirnOpaqueValue):
    """Deprecated shim over :meth:`ToolFactory.validate_arguments`."""

    def __init__(self) -> None:
        warnings.warn(
            "ArgumentValidator is deprecated (ADR agents-speaks-core WS1): a tool call's "
            "arguments are validated by the call knot's own adapters; use "
            "ToolFactory.validate_arguments() for the machine-readable detail",
            DeprecationWarning,
            stacklevel=2,
        )

    def validate(self, call: ToolCall, tool: Any) -> ToolResult | None:
        """Validate ``call.arguments`` against ``tool``'s declaration.

        Returns ``None`` when the arguments satisfy the declaration, else an
        error :class:`ToolResult` carrying the ``{argument: reason}`` detail.
        """
        factory = ToolFactory.of(tool)
        detail = factory.validate_arguments(factory.resolve_arguments(call.arguments))
        if not detail:
            return None
        error = ToolArgumentValidationError(
            tool_name=factory.name, detail=detail, call_id=call.call_id
        )
        return ToolResult(call_id=call.call_id, result=None, error=str(error))
