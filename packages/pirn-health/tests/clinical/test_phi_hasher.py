"""Unit tests for :class:`PhiHasher`."""

from __future__ import annotations

import unittest

from pirn_health.clinical.phi_hasher import PhiHasher


class TestHashIdentifier(unittest.TestCase):
    def test_stable_for_same_salt_and_value(self) -> None:
        assert PhiHasher.hash_identifier("seed", "P1") == PhiHasher.hash_identifier("seed", "P1")

    def test_differs_by_salt(self) -> None:
        assert PhiHasher.hash_identifier("seed-a", "P1") != PhiHasher.hash_identifier(
            "seed-b", "P1"
        )

    def test_differs_by_value(self) -> None:
        assert PhiHasher.hash_identifier("seed", "P1") != PhiHasher.hash_identifier("seed", "P2")

    def test_returns_sixteen_char_token(self) -> None:
        assert len(PhiHasher.hash_identifier("seed", "P1")) == 16
