from __future__ import annotations

import unittest

from pirn.core.identity.chained_identity_resolver import ChainedIdentityResolver
from pirn.core.identity.null_identity_resolver import NullIdentityResolver
from pirn.core.identity.static_identity_resolver import StaticIdentityResolver


class TestChainedIdentityResolver(unittest.TestCase):
    def test_returns_first_non_none(self) -> None:
        chain = ChainedIdentityResolver([NullIdentityResolver(), StaticIdentityResolver("x")])
        self.assertEqual(chain.resolve(), "x")

    def test_stops_at_first_match(self) -> None:
        chain = ChainedIdentityResolver([
            StaticIdentityResolver("first"),
            StaticIdentityResolver("second"),
        ])
        self.assertEqual(chain.resolve(), "first")

    def test_returns_none_when_all_null(self) -> None:
        chain = ChainedIdentityResolver([NullIdentityResolver(), NullIdentityResolver()])
        self.assertIsNone(chain.resolve())

    def test_empty_chain_returns_none(self) -> None:
        self.assertIsNone(ChainedIdentityResolver([]).resolve())
