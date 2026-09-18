from __future__ import annotations

import unittest

from pirn.exceptions.connector_usage_error import ConnectorUsageError
from pirn.exceptions.pirn_error import PirnError


class TestConnectorUsageError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(ConnectorUsageError, PirnError))

    def test_is_runtime_error_so_existing_handlers_still_catch_it(self) -> None:
        self.assertTrue(issubclass(ConnectorUsageError, RuntimeError))

    def test_message_preserved(self) -> None:
        err = ConnectorUsageError("already inside a transaction")
        self.assertEqual(str(err), "already inside a transaction")

    def test_caught_as_pirn_error(self) -> None:
        with self.assertRaises(PirnError):
            raise ConnectorUsageError("x")
