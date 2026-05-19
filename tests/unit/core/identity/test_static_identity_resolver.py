from __future__ import annotations

import unittest

from pirn.core.identity.static_identity_resolver import StaticIdentityResolver


class TestStaticIdentityResolver(unittest.TestCase):
    def test_returns_configured_actor(self) -> None:
        self.assertEqual(StaticIdentityResolver("svc-ingest").resolve(), "svc-ingest")

    def test_unconditional(self) -> None:
        resolver = StaticIdentityResolver("fixed")
        self.assertEqual(resolver.resolve(), "fixed")
        self.assertEqual(resolver.resolve(), "fixed")
