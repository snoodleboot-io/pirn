"""Unit tests for :class:`ProfileKey`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.profile_key import ProfileKey


class TestProfileKey(unittest.TestCase):
    def test_storage_key_is_session_independent(self) -> None:
        with_session = ProfileKey(namespace="user", subject_id="u1", session_id="s1")
        without_session = ProfileKey(namespace="user", subject_id="u1")
        assert with_session.storage_key == without_session.storage_key == "profile:user:u1"

    def test_entity_namespace_storage_key(self) -> None:
        key = ProfileKey(namespace="entity", subject_id="acme")
        assert key.storage_key == "profile:entity:acme"

    def test_rejects_bad_namespace(self) -> None:
        with self.assertRaises(ValueError):
            ProfileKey(namespace="org", subject_id="x")  # type: ignore[arg-type]

    def test_rejects_empty_subject(self) -> None:
        with self.assertRaises(TypeError):
            ProfileKey(namespace="user", subject_id="")
