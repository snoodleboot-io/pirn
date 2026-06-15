"""``ToolCallValidator`` — validate a :class:`ToolCall` against a :class:`Tool`'s schema.

Validates the ToolCall's arguments against the tool's ``parameters_schema``
before invocation. Raises :exc:`ValueError` on schema mismatch. Returns
the validated :class:`ToolCall` unchanged on success.

Algorithm:
    1. Validate that ``tool_call`` is a :class:`ToolCall`.
    2. Build a name-keyed registry from the supplied ``tools`` sequence.
    3. Look up the tool by name; raise ``ValueError`` if not found.
    4. Walk the tool's ``parameters_schema`` and check required fields are present,
       no extra fields exist when ``additionalProperties`` is ``False``, and each
       value's JSON type matches the schema declaration.
    5. Return the original ``tool_call`` unchanged on success.


References:
    - JSON Schema specification: https://json-schema.org/draft/2020-12/json-schema-validation
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall


class ToolCallValidator(Knot):
    """Validate a ToolCall's arguments against the tool's parameters_schema."""

    def __init__(
        self,
        *,
        tool_call: Knot | ToolCall,
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tool_call=tool_call, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        tool_call: ToolCall,
        tools: Sequence[Tool],
        **_: Any,
    ) -> ToolCall:
        """Validate the ToolCall arguments against the registered tool's schema.

        Args:
            tool_call: The ToolCall to validate before execution.
            tools: The sequence of Tool instances to validate against.

        Returns:
            The original ToolCall unchanged when validation passes.

        Raises:
            TypeError: If tool_call is not a ToolCall or any element of tools is not a Tool.
            ValueError: If the tool is not found or the arguments fail schema validation.
        """
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolCallValidator: tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
        tool_registry: dict[str, Tool] = {tool.name: tool for tool in tool_list}

        if not isinstance(tool_call, ToolCall):
            raise TypeError(
                f"ToolCallValidator: tool_call must be a ToolCall, got {type(tool_call).__name__}"
            )
        tool = tool_registry.get(tool_call.tool_name)
        if tool is None:
            raise ValueError(f"ToolCallValidator: unknown tool '{tool_call.tool_name}'")
        schema = tool.parameters_schema
        self._validate_against_schema(tool_call.arguments, schema, tool_call.tool_name)
        return tool_call

    def _validate_against_schema(
        self,
        arguments: Mapping[str, Any],
        schema: Mapping[str, Any],
        tool_name: str,
    ) -> None:
        schema_type = schema.get("type")
        if schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            for req_field in required:
                if req_field not in arguments:
                    raise ValueError(
                        f"ToolCallValidator: tool '{tool_name}' requires "
                        f"argument '{req_field}' which is missing"
                    )
            for arg_name, arg_value in arguments.items():
                if arg_name not in properties:
                    additional = schema.get("additionalProperties", True)
                    if additional is False:
                        raise ValueError(
                            f"ToolCallValidator: tool '{tool_name}' does not "
                            f"accept argument '{arg_name}'"
                        )
                    continue
                prop_schema = properties[arg_name]
                self._validate_type(arg_name, arg_value, prop_schema, tool_name)

    def _validate_type(
        self,
        field: str,
        value: Any,
        prop_schema: Mapping[str, Any],
        tool_name: str,
    ) -> None:
        expected_type = prop_schema.get("type")
        if expected_type is None:
            return
        type_map: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(expected_type)
        if python_type is None:
            return
        if expected_type == "integer" and isinstance(value, bool):
            raise ValueError(
                f"ToolCallValidator: tool '{tool_name}' argument '{field}' "
                f"must be integer, got bool"
            )
        if not isinstance(value, python_type):
            raise ValueError(
                f"ToolCallValidator: tool '{tool_name}' argument '{field}' "
                f"must be {expected_type}, got {type(value).__name__}"
            )
