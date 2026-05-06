from __future__ import annotations

import asyncio
import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory, knot
from pirn.core.parameter import Parameter


class TestKnotFactory(unittest.TestCase):
    def test_create_from_async_function(self) -> None:
        async def add(x: int, y: int, **_: Any) -> int:
            return x + y

        factory = KnotFactory.create(add)
        self.assertIsInstance(factory, KnotFactory)
        self.assertIs(factory.fn, add)
        self.assertTrue(issubclass(factory.knot_class, Knot))

    def test_create_from_sync_function(self) -> None:
        def double(x: int, **_: Any) -> int:
            return x * 2

        factory = KnotFactory.create(double)
        self.assertIsInstance(factory, KnotFactory)
        self.assertTrue(issubclass(factory.knot_class, Knot))

    def test_factory_name_mirrors_function(self) -> None:
        async def my_func(**_: Any) -> None:
            pass

        factory = KnotFactory.create(my_func)
        self.assertEqual(factory.__name__, "my_func")

    def test_factory_doc_mirrors_function(self) -> None:
        async def documented(**_: Any) -> None:
            """My docstring."""

        factory = KnotFactory.create(documented)
        self.assertEqual(factory.__doc__, "My docstring.")

    def test_factory_call_constructs_knot(self) -> None:
        async def add(x: int, y: int, **_: Any) -> int:
            return x + y

        factory = KnotFactory.create(add)
        px = Parameter("x", int, _config=KnotConfig(id="x"))
        py = Parameter("y", int, _config=KnotConfig(id="y"))
        node = factory(x=px, y=py, _config=KnotConfig(id="add"))
        self.assertIsInstance(node, Knot)
        self.assertEqual(node.knot_id, "add")

    def test_factory_repr(self) -> None:
        async def my_fn(**_: Any) -> None:
            pass

        factory = KnotFactory.create(my_fn)
        self.assertIn("KnotFactory", repr(factory))
        self.assertIn("my_fn", repr(factory))

    def test_factory_wrapped_attribute(self) -> None:
        async def my_fn(**_: Any) -> None:
            pass

        factory = KnotFactory.create(my_fn)
        self.assertIs(factory.__wrapped__, my_fn)


class TestKnotDecorator(unittest.TestCase):
    def test_decorator_bare(self) -> None:
        @knot
        async def add(x: int, **_: Any) -> int:
            return x + 1

        self.assertIsInstance(add, KnotFactory)

    def test_decorator_produces_working_knot(self) -> None:
        @knot
        async def triple(x: int, **_: Any) -> int:
            return x * 3

        px = Parameter("x", int, _config=KnotConfig(id="x"))
        node = triple(x=px, _config=KnotConfig(id="triple"))
        result = asyncio.run(node({"x": 4}))
        from pirn.core.ok import Ok

        self.assertIsInstance(result, Ok)
        self.assertEqual(result.value, 12)

    def test_decorator_sync_function_runs_in_thread(self) -> None:
        @knot
        def sync_add(x: int, **_: Any) -> int:
            return x + 10

        px = Parameter("x", int, _config=KnotConfig(id="x"))
        node = sync_add(x=px, _config=KnotConfig(id="sync"))
        result = asyncio.run(node({"x": 5}))
        from pirn.core.ok import Ok

        self.assertIsInstance(result, Ok)
        self.assertEqual(result.value, 15)

    def test_decorator_exposes_knot_class(self) -> None:
        @knot
        async def my_knot(**_: Any) -> None:
            pass

        self.assertTrue(issubclass(my_knot.knot_class, Knot))

    def test_decorator_with_parens_no_args(self) -> None:
        factory = knot(None)
        self.assertTrue(callable(factory))
