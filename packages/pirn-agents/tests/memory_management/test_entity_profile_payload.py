"""Unit tests for :class:`EntityProfile` as ``Payload[EntityProfileFrame, Mapping]`` (PIR-874)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pirn.core.payload import Payload

from pirn_agents.memory.management.entity_profile import EntityProfile
from pirn_agents.memory.management.entity_profile_frame import EntityProfileFrame
from pirn_agents.memory.management.profile_key import ProfileKey
from tests.memory_management.conftest import make_provenance


def _profile(**overrides: object) -> EntityProfile:
    kwargs: dict[str, object] = {
        "key": ProfileKey(namespace="user", subject_id="u1"),
        "fields": {"name": "Ada"},
        "provenance": make_provenance(source="profile_updater"),
        "updated_at": datetime(2026, 5, 1, tzinfo=UTC),
        "session_ids": ("s1",),
    }
    kwargs.update(overrides)
    return EntityProfile(**kwargs)  # type: ignore[arg-type]


class TestEntityProfilePayload:
    def test_is_a_payload_with_frame_and_data(self) -> None:
        profile = _profile()

        assert isinstance(profile, Payload)
        assert isinstance(profile.metadata, EntityProfileFrame)
        assert profile.metadata.key == ProfileKey(namespace="user", subject_id="u1")
        assert profile.metadata.updated_at == datetime(2026, 5, 1, tzinfo=UTC)
        assert profile.metadata.session_ids == ("s1",)
        assert profile.metadata.provenance.source == "profile_updater"
        assert profile.data == {"name": "Ada"}

    def test_audit_dict_has_both_halves(self) -> None:
        audit = _profile()._pirn_audit_dict()

        assert audit["subject_id"] == "u1"
        assert audit["session_ids"] == ["s1"]
        assert audit["fields"] == {"name": "Ada"}

    def test_equality_is_structural(self) -> None:
        assert _profile() == _profile()
        assert _profile() != _profile(fields={"name": "Bob"})
        assert _profile() != _profile(session_ids=("s1", "s2"))

    def test_rejects_wrong_types(self) -> None:
        with pytest.raises(TypeError):
            _profile(key="nope")
