from __future__ import annotations

import unittest

from pirn.core.ok import Ok


class TestOk(unittest.TestCase):
    def test_is_ok_true(self):
        ok = Ok(value=42)
        self.assertTrue(ok.is_ok)

    def test_is_err_false(self):
        ok = Ok(value=42)
        self.assertFalse(ok.is_err)

    def test_is_skipped_false(self):
        ok = Ok(value=42)
        self.assertFalse(ok.is_skipped)

    def test_unwrap_returns_value(self):
        ok = Ok(value="hello")
        self.assertEqual(ok.unwrap(), "hello")

    def test_value_stored(self):
        ok = Ok(value=[1, 2, 3])
        self.assertEqual(ok.value, [1, 2, 3])

    def test_frozen(self):
        ok = Ok(value=1)
        with self.assertRaises(Exception):
            ok.value = 2  # type: ignore[misc]

    def test_none_value(self):
        ok = Ok(value=None)
        self.assertIsNone(ok.unwrap())

    def test_dict_value(self):
        data = {"a": 1}
        ok = Ok(value=data)
        self.assertEqual(ok.unwrap(), data)
