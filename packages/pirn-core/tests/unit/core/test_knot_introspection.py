"""``Knot``'s public introspection API: what a knot class accepts (PIR-872).

A wrapper that constructs a knot class it did not write (a tool capability, an
agent-as-tool) reads ``reserved_kwargs()``, ``declared_input_schema()`` and
``input_annotations()`` instead of ``Knot``'s protected machinery.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_factory import KnotFactory

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}


class IntrospectionHinted(Knot):
    async def process(self, count: Knot | int, label, ratio: float | None = None, **_: Any) -> str:
        return f"{label}:{count}:{ratio}"


async def _echo(**arguments: Any) -> dict[str, Any]:
    return dict(arguments)


class TestReservedKwargs(unittest.TestCase):
    def test_names_the_framework_constructor_kwargs(self) -> None:
        # Act.
        reserved = Knot.reserved_kwargs()

        # Assert.
        self.assertEqual(reserved, frozenset({"_config", "tapestry"}))

    def test_a_subclass_reports_the_same_names(self) -> None:
        self.assertEqual(IntrospectionHinted.reserved_kwargs(), Knot.reserved_kwargs())


class TestDeclaredInputSchema(unittest.TestCase):
    def test_a_hinted_class_has_no_declared_schema(self) -> None:
        self.assertIsNone(IntrospectionHinted.declared_input_schema())

    def test_a_schema_declared_class_returns_its_schema(self) -> None:
        # Arrange.
        knot_class = KnotFactory.from_schema("introspection_echo", _SCHEMA, _echo).knot_class

        # Act.
        schema = knot_class.declared_input_schema()

        # Assert.
        self.assertIsNotNone(schema)
        assert schema is not None
        self.assertEqual(dict(schema["properties"]), {"query": {"type": "string"}})
        self.assertEqual(list(schema["required"]), ["query"])


class TestInputAnnotations(unittest.TestCase):
    def test_maps_each_named_input_to_its_validation_annotation(self) -> None:
        # Act.
        annotations = IntrospectionHinted.input_annotations()

        # Assert: ``Knot | int`` validates as ``int``; unannotated is ``Any``;
        # ``self`` and ``**_`` are not inputs.
        self.assertEqual(annotations, {"count": int, "label": Any, "ratio": float | None})

    def test_agrees_with_the_rendered_json_schema(self) -> None:
        # Act.
        properties = IntrospectionHinted.input_json_schema()["properties"]

        # Assert: the model-facing schema is rendered from the same inputs.
        self.assertEqual(set(properties), set(IntrospectionHinted.input_annotations()))
