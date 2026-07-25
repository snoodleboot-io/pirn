"""Unit tests for :class:`EntityProfile`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.memory_management.entity_profile import EntityProfile
from pirn_agents.memory_management.profile_key import ProfileKey
from tests.memory_management.conftest import make_provenance


def _profile() -> EntityProfile:
    return EntityProfile(
        key=ProfileKey(namespace="user", subject_id="u1"),
        fields={"name": "Ada", "prefs": {"theme": "dark"}},
        provenance=make_provenance(source="profile_updater"),
        updated_at=datetime(2026, 5, 1, tzinfo=UTC),
        session_ids=("s1", "s2"),
    )


class TestEntityProfile(unittest.TestCase):
    def test_payload_round_trips(self) -> None:
        profile = _profile()
        restored = EntityProfile.from_payload(profile.to_payload())
        assert restored == profile

    def test_rejects_non_key(self) -> None:
        with self.assertRaises(TypeError):
            EntityProfile(
                key="bad",  # type: ignore[arg-type]
                fields={},
                provenance=make_provenance(),
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_from_payload_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            EntityProfile.from_payload("bad")
