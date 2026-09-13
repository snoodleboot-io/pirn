"""Unit tests for ``JsonSchemaTypeBuilder`` (ADR agents-speaks-core, WS0).

Each JSON-schema shape becomes a Python type that a pydantic ``TypeAdapter``
validates the way the schema says; the tests validate values through the
adapter rather than inspecting the type, since the adapter's behaviour is
the contract.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from pydantic import TypeAdapter, ValidationError

from pirn.core.json_schema_type_builder import JsonSchemaTypeBuilder


def _adapter(fragment: Any, root: dict[str, Any] | None = None) -> TypeAdapter[Any]:
    return TypeAdapter(JsonSchemaTypeBuilder.python_type(fragment, root=root))


class TestScalars(unittest.TestCase):
    def test_string(self) -> None:
        adapter = _adapter({"type": "string"})
        self.assertEqual(adapter.validate_python("a"), "a")
        with self.assertRaises(ValidationError):
            adapter.validate_python(1)

    def test_integer_rejects_floats_with_fractions(self) -> None:
        adapter = _adapter({"type": "integer"})
        self.assertEqual(adapter.validate_python(3), 3)
        with self.assertRaises(ValidationError):
            adapter.validate_python(3.5)

    def test_number_accepts_ints(self) -> None:
        self.assertEqual(_adapter({"type": "number"}).validate_python(2), 2.0)

    def test_boolean(self) -> None:
        adapter = _adapter({"type": "boolean"})
        self.assertIs(adapter.validate_python(True), True)
        with self.assertRaises(ValidationError):
            adapter.validate_python("maybe")

    def test_null(self) -> None:
        adapter = _adapter({"type": "null"})
        self.assertIsNone(adapter.validate_python(None))
        with self.assertRaises(ValidationError):
            adapter.validate_python(0)

    def test_empty_fragment_accepts_anything(self) -> None:
        self.assertEqual(_adapter({}).validate_python({"x": [1]}), {"x": [1]})

    def test_true_fragment_accepts_anything(self) -> None:
        self.assertEqual(_adapter(True).validate_python(7), 7)

    def test_unknown_type_accepts_anything(self) -> None:
        self.assertEqual(_adapter({"type": "money"}).validate_python("$1"), "$1")


class TestEnumsAndUnions(unittest.TestCase):
    def test_enum_is_a_literal(self) -> None:
        adapter = _adapter({"type": "string", "enum": ["a", "b"]})
        self.assertEqual(adapter.validate_python("a"), "a")
        with self.assertRaises(ValidationError):
            adapter.validate_python("c")

    def test_const_is_a_single_literal(self) -> None:
        adapter = _adapter({"const": 42})
        self.assertEqual(adapter.validate_python(42), 42)
        with self.assertRaises(ValidationError):
            adapter.validate_python(41)

    def test_type_list_with_null_is_nullable(self) -> None:
        adapter = _adapter({"type": ["string", "null"]})
        self.assertIsNone(adapter.validate_python(None))
        self.assertEqual(adapter.validate_python("x"), "x")
        with self.assertRaises(ValidationError):
            adapter.validate_python(1)

    def test_openapi_nullable_flag(self) -> None:
        adapter = _adapter({"type": "integer", "nullable": True})
        self.assertIsNone(adapter.validate_python(None))
        self.assertEqual(adapter.validate_python(1), 1)

    def test_any_of(self) -> None:
        adapter = _adapter({"anyOf": [{"type": "integer"}, {"type": "string"}]})
        self.assertEqual(adapter.validate_python("s"), "s")
        self.assertEqual(adapter.validate_python(1), 1)
        with self.assertRaises(ValidationError):
            adapter.validate_python([1])

    def test_one_of_with_null(self) -> None:
        adapter = _adapter({"oneOf": [{"type": "boolean"}, {"type": "null"}]})
        self.assertIsNone(adapter.validate_python(None))
        self.assertIs(adapter.validate_python(False), False)


class TestArrays(unittest.TestCase):
    def test_items_are_validated(self) -> None:
        adapter = _adapter({"type": "array", "items": {"type": "integer"}})
        self.assertEqual(adapter.validate_python([1, 2]), [1, 2])
        with self.assertRaises(ValidationError):
            adapter.validate_python(["a"])

    def test_untyped_items_accept_anything(self) -> None:
        self.assertEqual(_adapter({"type": "array"}).validate_python([1, "a"]), [1, "a"])

    def test_item_bounds(self) -> None:
        adapter = _adapter({"type": "array", "items": {"type": "integer"}, "maxItems": 1})
        with self.assertRaises(ValidationError):
            adapter.validate_python([1, 2])


class TestObjects(unittest.TestCase):
    def test_properties_become_a_typed_dict(self) -> None:
        adapter = _adapter(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name"],
            }
        )
        self.assertEqual(adapter.validate_python({"name": "n"}), {"name": "n"})
        self.assertEqual(adapter.validate_python({"name": "n", "age": 3}), {"name": "n", "age": 3})
        with self.assertRaises(ValidationError):
            adapter.validate_python({"age": 3})
        with self.assertRaises(ValidationError):
            adapter.validate_python({"name": "n", "age": "x"})

    def test_unknown_keys_are_kept_by_default(self) -> None:
        adapter = _adapter({"type": "object", "properties": {"a": {"type": "integer"}}})
        self.assertEqual(adapter.validate_python({"a": 1, "b": 2}), {"a": 1, "b": 2})

    def test_additional_properties_false_refuses_unknown_keys(self) -> None:
        adapter = _adapter(
            {
                "type": "object",
                "properties": {"a": {"type": "integer"}},
                "additionalProperties": False,
            }
        )
        with self.assertRaises(ValidationError):
            adapter.validate_python({"a": 1, "b": 2})

    def test_object_without_properties_is_a_dict(self) -> None:
        adapter = _adapter({"type": "object"})
        self.assertEqual(adapter.validate_python({"k": [1]}), {"k": [1]})
        with self.assertRaises(ValidationError):
            adapter.validate_python(["not", "a", "dict"])

    def test_additional_properties_schema_types_the_values(self) -> None:
        adapter = _adapter({"type": "object", "additionalProperties": {"type": "integer"}})
        self.assertEqual(adapter.validate_python({"k": 1}), {"k": 1})
        with self.assertRaises(ValidationError):
            adapter.validate_python({"k": "v"})

    def test_properties_without_type_imply_an_object(self) -> None:
        adapter = _adapter({"properties": {"a": {"type": "integer"}}, "required": ["a"]})
        with self.assertRaises(ValidationError):
            adapter.validate_python({})

    def test_nested_objects(self) -> None:
        adapter = _adapter(
            {
                "type": "object",
                "properties": {
                    "inner": {
                        "type": "object",
                        "properties": {"n": {"type": "integer"}},
                        "required": ["n"],
                    }
                },
                "required": ["inner"],
            }
        )
        self.assertEqual(adapter.validate_python({"inner": {"n": 1}}), {"inner": {"n": 1}})
        with self.assertRaises(ValidationError):
            adapter.validate_python({"inner": {}})


class TestRefs(unittest.TestCase):
    def test_local_defs_ref_is_resolved(self) -> None:
        root = {
            "$defs": {"Id": {"type": "string", "minLength": 1}},
            "type": "object",
            "properties": {"id": {"$ref": "#/$defs/Id"}},
        }
        adapter = _adapter(root["properties"]["id"], root)
        self.assertEqual(adapter.validate_python("x"), "x")
        with self.assertRaises(ValidationError):
            adapter.validate_python("")

    def test_definitions_ref_is_resolved(self) -> None:
        root = {"definitions": {"N": {"type": "integer"}}}
        self.assertEqual(_adapter({"$ref": "#/definitions/N"}, root).validate_python(1), 1)

    def test_missing_ref_is_an_error(self) -> None:
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.python_type({"$ref": "#/$defs/Nope"}, root={"$defs": {}})

    def test_remote_ref_is_an_error(self) -> None:
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.python_type({"$ref": "https://x/y.json"}, root={})


class TestConstraints(unittest.TestCase):
    def test_numeric_bounds(self) -> None:
        adapter = _adapter({"type": "integer", "minimum": 1, "exclusiveMaximum": 10})
        self.assertEqual(adapter.validate_python(1), 1)
        for bad in (0, 10):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                adapter.validate_python(bad)

    def test_string_length_and_pattern(self) -> None:
        adapter = _adapter({"type": "string", "minLength": 2, "pattern": "^[a-z]+$"})
        self.assertEqual(adapter.validate_python("ab"), "ab")
        for bad in ("a", "AB"):
            with self.subTest(value=bad), self.assertRaises(ValidationError):
                adapter.validate_python(bad)


class TestObjectSchemaHelpers(unittest.TestCase):
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "k": {"type": "integer", "default": 5},
            "flag": {"type": "boolean"},
        },
        "required": ["q"],
    }

    def test_declared_required_and_defaults(self) -> None:
        self.assertEqual(JsonSchemaTypeBuilder.declared(self.schema), {"q", "k", "flag"})
        self.assertEqual(JsonSchemaTypeBuilder.required(self.schema), {"q"})
        self.assertEqual(JsonSchemaTypeBuilder.defaults(self.schema), {"k": 5})

    def test_input_adapters_follow_declaration_order(self) -> None:
        adapters = JsonSchemaTypeBuilder.input_adapters(self.schema)
        self.assertEqual(list(adapters), ["q", "k", "flag"])
        with self.assertRaises(ValidationError):
            adapters["k"].validate_python("five")

    def test_validate_input_schema_accepts_an_object_schema(self) -> None:
        out = JsonSchemaTypeBuilder.validate_input_schema(self.schema, reserved=frozenset())
        self.assertEqual(out["properties"], self.schema["properties"])

    def test_validate_input_schema_rejects_non_objects(self) -> None:
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.validate_input_schema({"type": "array"}, reserved=frozenset())
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.validate_input_schema("nope", reserved=frozenset())
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.validate_input_schema(
                {"type": "object", "properties": ["q"]}, reserved=frozenset()
            )

    def test_validate_input_schema_rejects_reserved_and_undeclared_names(self) -> None:
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.validate_input_schema(
                {"type": "object", "properties": {"_config": {}}}, reserved=frozenset({"_config"})
            )
        with self.assertRaises(TypeError):
            JsonSchemaTypeBuilder.validate_input_schema(
                {"type": "object", "properties": {}, "required": ["ghost"]}, reserved=frozenset()
            )
