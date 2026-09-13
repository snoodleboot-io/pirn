"""``Knot.input_json_schema()`` — the declaration a knot's hints imply (WS0).

The schema is rendered from exactly the annotations ``validate_io`` checks
against, so a model-facing declaration derived from it can never disagree
with what the engine will accept.
"""

from __future__ import annotations

import unittest
from typing import Annotated, Any

from pydantic import BaseModel, Field

from pirn.core.knot import Knot
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class _Client(PirnOpaqueValue):
    pass


class _Options(BaseModel):
    depth: int = 1


class _Search(Knot):
    async def process(
        self,
        query: str,
        limit: Annotated[int, Field(gt=0)] = 10,
        client: _Client | None = None,
        upstream: Knot | None = None,
        scale: Knot | float = 1.0,
        options: _Options | None = None,
        anything=None,
        **_: Any,
    ) -> list[str]:
        return [query]


class TestInputJsonSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _Search.input_json_schema()

    def test_is_an_object_schema_over_the_named_inputs(self) -> None:
        self.assertEqual(self.schema["type"], "object")
        self.assertEqual(
            list(self.schema["properties"]), ["query", "limit", "scale", "options", "anything"]
        )

    def test_parameters_without_defaults_are_required(self) -> None:
        self.assertEqual(self.schema["required"], ["query"])

    def test_plain_types_and_defaults(self) -> None:
        self.assertEqual(self.schema["properties"]["query"], {"type": "string"})
        self.assertEqual(self.schema["properties"]["limit"]["default"], 10)

    def test_annotated_constraints_are_kept(self) -> None:
        self.assertEqual(self.schema["properties"]["limit"]["exclusiveMinimum"], 0)
        self.assertEqual(self.schema["properties"]["limit"]["type"], "integer")

    def test_knot_or_scalar_hints_advertise_the_scalar(self) -> None:
        self.assertEqual(self.schema["properties"]["scale"], {"type": "number", "default": 1.0})

    def test_knot_typed_and_opaque_inputs_are_excluded(self) -> None:
        self.assertNotIn("upstream", self.schema["properties"])
        self.assertNotIn("client", self.schema["properties"])

    def test_the_catch_all_is_excluded(self) -> None:
        self.assertNotIn("_", self.schema["properties"])

    def test_unannotated_parameter_accepts_anything(self) -> None:
        self.assertEqual(self.schema["properties"]["anything"], {"default": None})

    def test_model_inputs_hoist_their_defs(self) -> None:
        options = self.schema["properties"]["options"]
        self.assertIn("_Options", self.schema["$defs"])
        self.assertIn("anyOf", options)
        self.assertEqual(self.schema["$defs"]["_Options"]["properties"]["depth"]["default"], 1)
        self.assertNotIn("$defs", options)


class TestInputJsonSchemaOtherShapes(unittest.TestCase):
    def test_knot_factory_class_derives_from_the_function(self) -> None:
        @knot
        async def scale(value: float, factor: float = 2.0, **_: Any) -> float:
            return value * factor

        schema = scale.knot_class.input_json_schema()
        self.assertEqual(schema["required"], ["value"])
        self.assertEqual(schema["properties"]["factor"], {"type": "number", "default": 2.0})

    def test_a_knot_with_no_inputs(self) -> None:
        self.assertEqual(
            Parameter.input_json_schema(), {"type": "object", "properties": {}, "required": []}
        )

    def test_a_non_json_default_is_omitted_but_still_optional(self) -> None:
        class _WithObjectDefault(Knot):
            async def process(self, marker: object = object(), **_: Any) -> None:
                return None

        schema = _WithObjectDefault.input_json_schema()
        self.assertEqual(schema["required"], [])
        self.assertNotIn("default", schema["properties"]["marker"])

    def test_an_all_opaque_union_is_excluded_but_a_mixed_one_is_kept(self) -> None:
        class _Mixed(Knot):
            async def process(self, a: _Client | str, b: _Client | Knot, **_: Any) -> None:
                return None

        properties = _Mixed.input_json_schema()["properties"]
        self.assertIn("a", properties)
        self.assertNotIn("b", properties)
