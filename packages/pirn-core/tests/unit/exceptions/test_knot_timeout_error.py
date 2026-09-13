from __future__ import annotations

import unittest

from pirn.exceptions.knot_timeout_error import KnotTimeoutError
from pirn.exceptions.pirn_error import PirnError


class TestKnotTimeoutError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(KnotTimeoutError, PirnError))

    def test_message_names_knot_and_limit(self) -> None:
        err = KnotTimeoutError("llm0", 2.5)
        self.assertIn("'llm0'", str(err))
        self.assertIn("2.5s", str(err))

    def test_exposes_knot_id_and_timeout(self) -> None:
        err = KnotTimeoutError("llm0", 2.5)
        self.assertEqual(err.knot_id, "llm0")
        self.assertEqual(err.timeout, 2.5)

    def test_raise_and_catch_as_pirn_error(self) -> None:
        with self.assertRaises(PirnError):
            raise KnotTimeoutError("k", 1.0)
