from __future__ import annotations

import unittest

from pirn.exceptions.nested_run_cycle_error import NestedRunCycleError
from pirn.exceptions.nesting_depth_exceeded_error import NestingDepthExceededError
from pirn.exceptions.pirn_error import PirnError


class TestNestingDepthExceededError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(NestingDepthExceededError, PirnError))

    def test_message_names_depth_limit_and_key(self) -> None:
        err = NestingDepthExceededError(depth=4, limit=3, path=("a.A",), key="b.B")
        self.assertIn("depth 4", str(err))
        self.assertIn("max_nesting_depth=3", str(err))
        self.assertIn("'b.B'", str(err))
        self.assertIn("['a.A']", str(err))

    def test_keyless_message_omits_the_by_clause(self) -> None:
        err = NestingDepthExceededError(depth=2, limit=1, path=(), key=None)
        self.assertNotIn(" by ", str(err))
        self.assertIsNone(err.key)

    def test_raise_and_catch_as_pirn_error(self) -> None:
        with self.assertRaises(PirnError):
            raise NestingDepthExceededError(depth=2, limit=1, path=(), key=None)


class TestNestedRunCycleError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(NestedRunCycleError, PirnError))

    def test_message_names_key_and_path(self) -> None:
        err = NestedRunCycleError(key="a.A", path=("a.A", "b.B"))
        self.assertIn("'a.A'", str(err))
        self.assertIn("['a.A', 'b.B']", str(err))
        self.assertEqual(err.key, "a.A")
        self.assertEqual(err.path, ("a.A", "b.B"))

    def test_raise_and_catch_as_pirn_error(self) -> None:
        with self.assertRaises(PirnError):
            raise NestedRunCycleError(key="a.A", path=())
