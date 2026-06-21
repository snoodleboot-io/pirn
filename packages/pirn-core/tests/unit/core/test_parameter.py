from __future__ import annotations

import unittest

from pirn.core.parameter import Parameter
from pirn.exceptions.unbound_parameter_error import UnboundParameterError


class TestParameterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_bound_value(self):
        p = Parameter("x", int)
        p.bind_value(99)
        self.assertEqual(await p.process(), 99)

    async def test_process_returns_default_when_not_bound(self):
        p = Parameter("y", str, default="hello")
        self.assertEqual(await p.process(), "hello")

    async def test_process_raises_when_no_value_no_default(self):
        p = Parameter("z", float)
        with self.assertRaises(UnboundParameterError) as ctx:
            await p.process()
        self.assertIn("z", str(ctx.exception))

    async def test_bind_value_overrides_default(self):
        p = Parameter("n", int, default=0)
        p.bind_value(42)
        self.assertEqual(await p.process(), 42)

    def test_spec_name_and_type(self):
        p = Parameter("threshold", float, description="A cutoff value")
        self.assertEqual(p.spec.name, "threshold")
        self.assertIs(p.spec.type_, float)
        self.assertEqual(p.spec.description, "A cutoff value")

    def test_has_default_false(self):
        p = Parameter("x", int)
        self.assertFalse(p.has_default)

    def test_has_default_true(self):
        p = Parameter("x", int, default=5)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default, 5)

    def test_default_raises_when_not_set(self):
        p = Parameter("x", int)
        with self.assertRaises(AttributeError):
            _ = p.default
