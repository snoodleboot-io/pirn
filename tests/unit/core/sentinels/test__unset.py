from __future__ import annotations

import unittest

from pirn.core.sentinels._unset import _Unset


class TestUnsetSentinel(unittest.TestCase):
    def test_sentinel_is_class(self):
        self.assertIsInstance(_Unset, type)

    def test_sentinel_identity(self):
        self.assertIs(_Unset, _Unset)

    def test_use_as_default_arg(self):
        def fn(value=_Unset):
            return value is _Unset

        self.assertTrue(fn())
        self.assertFalse(fn(42))

    def test_not_equal_to_none(self):
        self.assertIsNot(_Unset, None)

    def test_not_equal_to_false(self):
        self.assertIsNot(_Unset, False)

    def test_sentinel_not_an_instance(self):
        self.assertNotIsInstance(_Unset, _Unset)
