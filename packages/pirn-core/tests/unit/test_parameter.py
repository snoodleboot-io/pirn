"""Parameter tests."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


class _StandaloneTests(unittest.TestCase):
    def test_parameter_basics(self):
        p = Parameter("x", int)
        assert p.name == "x"
        assert p.type_ is int
        assert p.knot_id == "param:x"  # default id derived from name
        assert not p.has_default
    
    
    def test_parameter_with_default(self):
        p = Parameter("x", int, default=42)
        assert p.has_default
        assert p.default == 42
    
    
    def test_parameter_no_default_raises_on_default_access(self):
        p = Parameter("x", int)
        with self.assertRaises(AttributeError):
            _ = p.default
    
    
    def test_parameter_explicit_id(self):
        p = Parameter("x", int, _config=KnotConfig(id="my_param"))
        assert p.knot_id == "my_param"
    
    
    def test_parameter_bind_validates_type(self):
        from pydantic import ValidationError
    
        p = Parameter("x", int)
        assert p.bind(5) == 5
        # Pydantic coerces "5" to 5 by default.
        assert p.bind("5") == 5
        with self.assertRaises(ValidationError):
            p.bind("not a number")
    
    
    def test_parameter_bind_complex_type(self):
        from pydantic import ValidationError
    
        p = Parameter("xs", list[int])
        assert p.bind([1, 2, 3]) == [1, 2, 3]
        with self.assertRaises(ValidationError):
            p.bind("not a list")
    
    
    def test_parameter_self_registers(self):
        with Tapestry() as t:
            p = Parameter("x", int)
        assert t.get(p.knot_id) is p
    
    
    def test_parameter_no_parents(self):
        p = Parameter("x", int)
        assert p.parents == {}
    
    
    def test_parameter_immutable(self):
        p = Parameter("x", int)
        with self.assertRaises(AttributeError):
            p.foo = 1  # type: ignore[attr-defined]
