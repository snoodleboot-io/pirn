from __future__ import annotations

import unittest

from pirn.core.optional import Optional


class TestOptionalMixin(unittest.TestCase):
    def test_is_mixin_class(self):
        self.assertTrue(issubclass(Optional, object))

    def test_subclass_is_optional(self):
        class MyKnot(Optional):
            pass

        self.assertTrue(issubclass(MyKnot, Optional))
        self.assertIsInstance(MyKnot(), Optional)

    def test_no_methods_or_attributes(self):
        public = [k for k in vars(Optional) if not k.startswith("_")]
        self.assertEqual(public, [])

    def test_multiple_inheritance_mro(self):
        class Base:
            pass

        class MyKnot(Optional, Base):
            pass

        self.assertIn(Optional, MyKnot.__mro__)
        self.assertIn(Base, MyKnot.__mro__)
