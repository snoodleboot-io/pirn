"""``ArgumentValidator`` — check a call's arguments against a tool schema.

The validator implements a small, dependency-free SUBSET of JSON Schema —
enough to cover the schemas pirn tools declare, without pulling in
``jsonschema`` or any third-party package. The supported subset is:

Top level
    ``type: "object"`` (assumed; any other top-level type is not
    inspected and the arguments are accepted).
``required``
    A list of argument names. Any name absent from the call's arguments
    is reported with reason ``"missing_required"``.
``properties[name].type``
    A JSON-Schema type name mapped to python types for an ``isinstance``
    check:

    - ``"string"``  -> ``str``
    - ``"integer"`` -> ``int`` (but not ``bool``)
    - ``"number"``  -> ``int`` / ``float`` (but not ``bool``)
    - ``"boolean"`` -> ``bool``
    - ``"array"``   -> ``list`` / ``tuple``
    - ``"object"``  -> ``Mapping`` (e.g. ``dict``)

    A type mismatch is reported with reason
    ``"expected:<schema-type>,got:<python-type>"``. A property with no
    ``type`` (or an unrecognised type name) is accepted — the validator
    never over-rejects on types it does not model.
``additionalProperties``
    When explicitly ``false``, any argument name absent from
    ``properties`` is reported with reason ``"unexpected_property"``.
    Otherwise extra arguments are permitted (permissive default).

Nested schemas, ``enum``, ``format``, numeric bounds, and the rest of
JSON Schema are intentionally out of scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class ArgumentValidator(PirnOpaqueValue):
    """Stateless validator of :class:`ToolCall` arguments against a schema.

    Construct once and reuse; :meth:`validate` holds no per-call state.
    """

    def __init__(self) -> None:
        """Build the schema-type-name -> python-type check table.

        The table lives on the instance (not as a module constant) so the
        validator stays a self-contained IO-boundary value.
        """
        self._type_checks: dict[str, tuple[type[Any], ...]] = {
            "string": (str,),
            "integer": (int,),
            "number": (int, float),
            "boolean": (bool,),
            "array": (list, tuple),
            "object": (Mapping,),
        }

    def validate(self, call: ToolCall, tool: Tool) -> ToolResult | None:
        """Validate ``call.arguments`` against ``tool.parameters_schema``.

        Returns ``None`` when the arguments satisfy the schema — the
        caller may then dispatch the tool. Returns an error
        :class:`ToolResult` (``status=ERROR``) carrying a machine-readable
        detail when the arguments are invalid; the tool is never invoked
        here. No exception crosses the boundary.
        """
        schema = tool.parameters_schema
        detail = self._collect_errors(call.arguments, schema)
        if not detail:
            return None

        error = ToolArgumentValidationError(
            tool_name=tool.name,
            detail=detail,
            call_id=call.call_id,
        )
        return ToolResult(
            call_id=call.call_id,
            result=None,
            error=str(error),
            status=ToolStatus.ERROR,
        )

    def _collect_errors(
        self, arguments: Mapping[str, Any], schema: Mapping[str, Any]
    ) -> dict[str, str]:
        """Return an arg-name -> reason mapping of every violation found."""
        detail: dict[str, str] = {}

        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}

        required = schema.get("required")
        required = required if isinstance(required, (list, tuple)) else ()

        for name in required:
            if name not in arguments:
                detail[str(name)] = "missing_required"

        if schema.get("additionalProperties") is False:
            for name in arguments:
                if name not in properties:
                    detail.setdefault(name, "unexpected_property")

        for name, value in arguments.items():
            if name in detail:
                continue
            prop = properties.get(name)
            if not isinstance(prop, Mapping):
                continue
            reason = self._check_type(prop.get("type"), value)
            if reason is not None:
                detail[name] = reason

        return detail

    def _check_type(self, schema_type: Any, value: Any) -> str | None:
        """Return a reason string on type mismatch, or ``None`` if valid.

        Unknown/absent ``schema_type`` accepts any value. ``bool`` is
        rejected for the numeric types since ``bool`` is an ``int``
        subclass yet is not a valid ``integer``/``number`` argument.
        """
        if not isinstance(schema_type, str):
            return None
        expected = self._type_checks.get(schema_type)
        if expected is None:
            return None
        if schema_type in ("integer", "number") and isinstance(value, bool):
            return f"expected:{schema_type},got:{type(value).__name__}"
        if isinstance(value, expected):
            return None
        return f"expected:{schema_type},got:{type(value).__name__}"
