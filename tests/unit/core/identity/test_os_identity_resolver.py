from __future__ import annotations

import unittest

from pirn.core.identity.os_identity_resolver import OsIdentityResolver


class TestOsIdentityResolver(unittest.TestCase):
    def test_returns_non_empty_string(self) -> None:
        result = OsIdentityResolver().resolve()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_isinstance_identity_resolver(self) -> None:
        from pirn.core.identity.identity_resolver import IdentityResolver
        self.assertIsInstance(OsIdentityResolver(), IdentityResolver)
