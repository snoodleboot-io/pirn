from __future__ import annotations

import unittest

from pirn.exceptions.backend_capability_error import BackendCapabilityError
from pirn.exceptions.pirn_error import PirnError


class TestBackendCapabilityError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(BackendCapabilityError, PirnError))

    def test_is_runtime_error_so_existing_handlers_still_catch_it(self) -> None:
        self.assertTrue(issubclass(BackendCapabilityError, RuntimeError))

    def test_is_not_an_import_error(self) -> None:
        """The dependency is installed; the message must not read as "not installed"."""
        self.assertFalse(issubclass(BackendCapabilityError, ImportError))

    def test_message_preserved(self) -> None:
        err = BackendCapabilityError("pyedflib exposes no PHI setter")
        self.assertEqual(str(err), "pyedflib exposes no PHI setter")
