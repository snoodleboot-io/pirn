"""Tests for :class:`pirn_agents.tools.tool_declaration.ToolDeclaration` (PIR-706).

Two jobs here. First, the envelope itself: it carries the neutral
``{name, description, parameters}`` triple, validates its own fields, and
serialises to exactly the dict every provider adapter indexes into.

Second -- and the reason the class is worth having -- the wire shape. The
declaration dict is not an internal convenience: it is fed straight to a
:class:`pirn_agents.llm.provider_adapter.ProviderAdapter`, whose output becomes
the HTTP request body. So the JSON Schema inside ``parameters`` must be carried
through **verbatim**, including the details a re-serialising model would
destroy: ``required`` absent (not ``[]``) when a tool takes no arguments, no
injected ``title``, ``None`` values preserved, and ``$ref``/``$defs``/``x-*``
vendor keys untouched.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from pirn_agents.llm.anthropic_messages_tool_adapter import AnthropicMessagesToolAdapter
from pirn_agents.llm.openai_compatible_tool_adapter import OpenAICompatibleToolAdapter
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.toolset import Toolset


class VendorExtendedTool(Tool):
    """A tool whose schema is open, recursive and vendor-extended.

    Deliberately unrepresentable by any fixed model class -- exactly what an
    MCP server may hand us at runtime.
    """

    @property
    def name(self) -> str:
        return "vendor"

    @property
    def description(self) -> str:
        return "vendor-extended schema"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node": {"$ref": "#/$defs/node"},
                "nullable": {"type": ["string", "null"]},
                "novalue": None,
            },
            "$defs": {
                "node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/node"}}}
            },
            "x-vendor-hint": {"cache": True, "nested": [1, 2, {"deep": None}]},
            "additionalProperties": False,
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return None


class NoArgsTool(Tool):
    """A tool taking no arguments: ``required`` must stay ABSENT, not ``[]``."""

    @property
    def name(self) -> str:
        return "noargs"

    @property
    def description(self) -> str:
        return "takes nothing"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return None


class TestToolDeclarationPayload(unittest.TestCase):
    def test_payload_key_set_and_order_are_the_neutral_contract(self) -> None:
        declaration = ToolDeclaration(name="a", description="d", parameters={"type": "object"})

        payload = declaration.to_payload()

        assert list(payload) == ["name", "description", "parameters"]
        assert payload == {"name": "a", "description": "d", "parameters": {"type": "object"}}

    def test_payload_parameters_is_a_plain_dict(self) -> None:
        # Adapters and json.dumps both expect a real dict here.
        payload = ToolDeclaration(name="a", description="d", parameters={}).to_payload()
        assert isinstance(payload["parameters"], dict)

    def test_payload_copies_parameters_so_callers_cannot_mutate_the_tool(self) -> None:
        source: dict[str, Any] = {"type": "object"}
        payload = ToolDeclaration(name="a", description="d", parameters=source).to_payload()

        payload["parameters"]["type"] = "tampered"

        assert source == {"type": "object"}

    def test_round_trips_through_payload(self) -> None:
        declaration = ToolDeclaration(
            name="a", description="d", parameters={"type": "object", "properties": {}}
        )
        assert ToolDeclaration.from_payload(declaration.to_payload()) == declaration

    def test_from_payload_rejects_a_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="must be a Mapping"):
            ToolDeclaration.from_payload(["not", "a", "mapping"])

    def test_audit_dict_is_the_payload(self) -> None:
        declaration = ToolDeclaration(name="a", description="d", parameters={})
        assert declaration._pirn_audit_dict() == declaration.to_payload()


class TestToolDeclarationValidation(unittest.TestCase):
    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(TypeError, match="name"):
            ToolDeclaration(name="", description="d", parameters={})

    def test_rejects_a_non_str_description(self) -> None:
        # Routed through an ``Any`` local: the point is the RUNTIME guard, and
        # a bare literal here would just be a static type error.
        bad_description: Any = None
        with pytest.raises(TypeError, match="description"):
            ToolDeclaration(name="a", description=bad_description, parameters={})

    def test_rejects_non_mapping_parameters(self) -> None:
        bad_parameters: Any = []
        with pytest.raises(TypeError, match="parameters"):
            ToolDeclaration(name="a", description="d", parameters=bad_parameters)

    def test_is_immutable(self) -> None:
        declaration = ToolDeclaration(name="a", description="d", parameters={})
        with pytest.raises(FrozenInstanceError):
            declaration.__setattr__("name", "b")


class TestToolDeclarationFromTools(unittest.TestCase):
    def test_every_tool_exposes_a_declaration(self) -> None:
        declaration = NoArgsTool().declaration()

        assert declaration.name == "noargs"
        assert declaration.description == "takes nothing"
        assert declaration.parameters == {"type": "object", "properties": {}}

    def test_toolset_declarations_preserve_registration_order(self) -> None:
        toolset = Toolset([VendorExtendedTool(), NoArgsTool()])
        assert [d.name for d in toolset.declarations()] == ["vendor", "noargs"]

    def test_toolset_schema_is_the_serialised_declarations(self) -> None:
        toolset = Toolset([VendorExtendedTool(), NoArgsTool()])
        assert toolset.schema() == [d.to_payload() for d in toolset.declarations()]


class TestJsonSchemaIsCarriedVerbatim(unittest.TestCase):
    """The envelope is modelled; the schema inside it must not be."""

    def test_vendor_schema_survives_unchanged(self) -> None:
        tool = VendorExtendedTool()

        parameters = tool.declaration().to_payload()["parameters"]

        assert parameters == dict(tool.parameters_schema)
        assert parameters["properties"]["novalue"] is None
        assert parameters["$defs"]["node"]["properties"]["child"] == {"$ref": "#/$defs/node"}
        assert parameters["x-vendor-hint"] == {"cache": True, "nested": [1, 2, {"deep": None}]}

    def test_empty_required_is_omitted_not_emitted(self) -> None:
        parameters = NoArgsTool().declaration().to_payload()["parameters"]
        assert "required" not in parameters

    def test_no_title_is_injected(self) -> None:
        parameters = NoArgsTool().declaration().to_payload()["parameters"]
        assert "title" not in parameters


class TestNativeWireShapeIsUnchanged(unittest.TestCase):
    """Golden native declarations for both shipped adapters.

    These dicts are posted as the provider request body, so they are pinned
    whole rather than key-by-key.
    """

    def _toolset(self) -> Toolset:
        return Toolset([NoArgsTool()])

    def test_openai_compatible_native_declaration(self) -> None:
        native = ToolCallCodec(OpenAICompatibleToolAdapter()).encode_tools(self._toolset())

        assert native == [
            {
                "type": "function",
                "function": {
                    "name": "noargs",
                    "description": "takes nothing",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    def test_anthropic_messages_native_declaration(self) -> None:
        native = ToolCallCodec(AnthropicMessagesToolAdapter()).encode_tools(self._toolset())

        assert native == [
            {
                "name": "noargs",
                "description": "takes nothing",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

    def test_adapters_receive_a_plain_dict_not_the_envelope(self) -> None:
        # The adapter contract is dict-in/dict-out and third-party adapters do
        # hard key access; the typed envelope must not leak across that seam.
        seen: list[Any] = []

        class RecordingAdapter(OpenAICompatibleToolAdapter):
            def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
                seen.append(neutral_tool)
                return super().tool_to_native(neutral_tool)

        ToolCallCodec(RecordingAdapter()).encode_tools(self._toolset())

        assert len(seen) == 1
        assert type(seen[0]) is dict
        assert list(seen[0]) == ["name", "description", "parameters"]
