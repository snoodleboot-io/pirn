"""Unit tests for :class:`_PhiHasher`."""

from __future__ import annotations

import unittest

from pirn_health.clinical.phi_hasher import _PhiHasher


class TestHashIdentifier(unittest.TestCase):
    def test_stable_for_same_salt_and_value(self) -> None:
        assert _PhiHasher.hash_identifier("seed", "P1") == _PhiHasher.hash_identifier("seed", "P1")

    def test_differs_by_salt(self) -> None:
        assert _PhiHasher.hash_identifier("seed-a", "P1") != _PhiHasher.hash_identifier(
            "seed-b", "P1"
        )

    def test_differs_by_value(self) -> None:
        assert _PhiHasher.hash_identifier("seed", "P1") != _PhiHasher.hash_identifier("seed", "P2")

    def test_returns_sixteen_char_token(self) -> None:
        assert len(_PhiHasher.hash_identifier("seed", "P1")) == 16
