from __future__ import annotations

import unittest

from pirn.core.sentinels.unset import Unset


class TestUnsetSentinel(unittest.TestCase):
    def test_sentinel_is_class(self):
        self.assertIsInstance(Unset, type)

    def test_sentinel_identity(self):
        self.assertIs(Unset, Unset)

    def test_use_as_default_arg(self):
        def fn(value=Unset):
            return value is Unset

        self.assertTrue(fn())
        self.assertFalse(fn(42))

    def test_not_equal_to_none(self):
        self.assertIsNot(Unset, None)

    def test_not_equal_to_false(self):
        self.assertIsNot(Unset, False)

    def test_sentinel_not_an_instance(self):
        self.assertNotIsInstance(Unset, Unset)
