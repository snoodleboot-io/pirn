from __future__ import annotations

import unittest

from pirn.core.identity.null_identity_resolver import NullIdentityResolver


class TestNullIdentityResolver(unittest.TestCase):
    def test_always_returns_none(self) -> None:
        self.assertIsNone(NullIdentityResolver().resolve())
