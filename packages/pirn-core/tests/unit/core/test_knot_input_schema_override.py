"""Schema-declared knots: ``KnotFactory.from_schema`` and ``@knot(input_schema=)`` (WS0).

A knot built from a JSON object schema is wired, validated and run by the
same machinery as a hinted one: the schema's properties are its declared
inputs, ``required`` what construction must supply, ``default`` what fills
the rest, and each fragment the ``TypeAdapter`` that ``validate_io`` applies.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory, knot
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "default": 10},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["query"],
}


async def _search(**arguments: Any) -> dict[str, Any]:
    return dict(arguments)


def _sync_search(**arguments: Any) -> dict[str, Any]:
    return dict(arguments)


class TestFromSchemaConstruction(unittest.TestCase):
    def test_builds_a_factory_over_a_knot_subclass(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)
        self.assertIsInstance(factory, KnotFactory)
        self.assertTrue(issubclass(factory.knot_class, Knot))
        self.assertEqual(factory.knot_class.__name__, "search")
        self.assertIs(factory.fn, _search)

    def test_description_becomes_the_docstring(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search, description="Find.")
        self.assertEqual(factory.knot_class.__doc__, "Find.")

    def test_declared_inputs_come_from_the_schema(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
            query="q", _config=KnotConfig(id="s")
        )
        self.assertEqual(node.input_names, ("query", "limit", "tags"))

    def test_missing_required_input_fails_at_construction(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)
        with self.assertRaisesRegex(TypeError, r"missing required input\(s\) \['query'\]"):
            factory(limit=3, _config=KnotConfig(id="s"))

    def test_optional_inputs_may_be_omitted_and_defaults_fill_in(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
            query="q", _config=KnotConfig(id="s")
        )
        self.assertEqual(node.config_values, {"query": "q", "limit": 10})

    def test_unknown_input_fails_at_construction(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)
        with self.assertRaisesRegex(TypeError, "unknown non-Knot kwarg"):
            factory(query="q", page=2, _config=KnotConfig(id="s"))

    def test_config_values_are_validated_against_the_schema(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)
        with self.assertRaisesRegex(TypeError, "limit.*failed validation"):
            factory(query="q", limit=0, _config=KnotConfig(id="s"))
        with self.assertRaisesRegex(TypeError, "query.*failed validation"):
            factory(query="", _config=KnotConfig(id="s"))

    def test_invalid_schema_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            KnotFactory.from_schema("bad", {"type": "array"}, _search)
        with self.assertRaises(TypeError):
            KnotFactory.from_schema(
                "bad", {"type": "object", "properties": {"tapestry": {}}}, _search
            )

    def test_input_json_schema_returns_the_declaration(self) -> None:
        factory = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)
        schema = factory.knot_class.input_json_schema()
        self.assertEqual(schema, SEARCH_SCHEMA)
        self.assertIsNot(schema, SEARCH_SCHEMA)


class TestFromSchemaExecution(unittest.IsolatedAsyncioTestCase):
    async def test_process_receives_the_validated_inputs(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
            query="q", tags=["a"], _config=KnotConfig(id="s")
        )
        result = await node({})
        self.assertEqual(result, Ok(value={"query": "q", "limit": 10, "tags": ["a"]}))

    async def test_a_parent_knot_supplies_an_input(self) -> None:
        with Tapestry() as t:
            q = Parameter("q", str, _config=KnotConfig(id="q"))
            KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
                query=q, limit=2, _config=KnotConfig(id="s")
            )
        result = await t.run(RunRequest(parameters={"q": "hello"}))
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["s"], {"query": "hello", "limit": 2})

    async def test_a_bad_parent_value_is_an_err(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
            query="q", _config=KnotConfig(id="s")
        )
        result = await node({"query": 123})
        self.assertIsInstance(result, Err)

    async def test_sync_process_runs_in_a_thread(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _sync_search)(
            query="q", _config=KnotConfig(id="s")
        )
        result = await node({})
        self.assertEqual(result, Ok(value={"query": "q", "limit": 10}))

    async def test_validate_io_false_skips_schema_validation(self) -> None:
        node = KnotFactory.from_schema("search", SEARCH_SCHEMA, _search)(
            query="q", limit=0, _config=KnotConfig(id="s", validate_io=False)
        )
        result = await node({})
        self.assertEqual(result, Ok(value={"query": "q", "limit": 0}))


class TestKnotDecoratorWithSchema(unittest.TestCase):
    def test_decorator_with_schema_declares_inputs(self) -> None:
        @knot(input_schema=SEARCH_SCHEMA)
        async def search(**arguments: Any) -> dict[str, Any]:
            return dict(arguments)

        self.assertIsInstance(search, KnotFactory)
        self.assertEqual(search.knot_class.__name__, "search")
        node = search(query="q", _config=KnotConfig(id="s"))
        self.assertEqual(asyncio.run(node({})), Ok(value={"query": "q", "limit": 10}))

    def test_decorator_without_schema_is_unchanged(self) -> None:
        @knot
        async def add(x: int, **_: Any) -> int:
            return x + 1

        self.assertIsNone(add.knot_class._input_schema_override)
        self.assertEqual(add.knot_class.input_json_schema()["required"], ["x"])
