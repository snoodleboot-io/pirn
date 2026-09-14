"""F14 → F27 seam closure: a durable-session identity drives F27 profile keying.

F27's ``ProfileKey`` documents ``session_id`` as the *F14 plug point*. This test
closes that seam end-to-end: an F14 durable-session identity (now a chain of
engine runs linked by ``_parent_run_id`` -- see
``pirn_agents.sessions.session_chain`` -- rather than a persisted checkpoint)
is fed, unchanged, into an F27 :class:`ProfileKey` and driven through the F27
:class:`CrossSessionProfileUpdater`. The session lifecycle thus keys the profile
update — without F14 importing F27 machinery or F27 inventing session machinery.
No F27 source is modified.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.management.cross_session_profile_updater import (
    CrossSessionProfileUpdater,
)
from pirn_agents.memory.management.profile_key import ProfileKey
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore
from pirn_agents.sessions.session_identity import SessionIdentity


class TestF27SessionSeam:
    async def test_session_identity_drives_profile_keying(self) -> None:
        # Arrange — an F14 durable session identity.
        identity = SessionIdentity(
            session_id="sess-42", created_at=datetime(2026, 7, 12, tzinfo=UTC)
        )

        # Act — feed that F14 session id into the F27 profile seam, unchanged.
        profile_store = KeyedLineageStore(history=InMemoryHistory(), data_store=InMemoryDataStore())
        with Tapestry():
            updater = CrossSessionProfileUpdater(
                key=ProfileKey(namespace="user", subject_id="u1"),
                incoming_fields={},
                store=profile_store,
                now=datetime(2026, 7, 12, tzinfo=UTC),
                _config=KnotConfig(id="cspu"),
            )
        profile = await updater.process(
            key=ProfileKey(namespace="user", subject_id="u1", session_id=identity.session_id),
            incoming_fields={"greeted": True},
            store=profile_store,
            now=datetime(2026, 7, 12, tzinfo=UTC),
        )

        # Assert — the F14 session identity keyed the F27 profile update, and the
        # subject-scoped storage key stays session-independent (profiles persist
        # across sessions).
        assert profile.session_ids == ("sess-42",)
        assert profile.fields == {"greeted": True}
        assert await profile_store.get(namespace="profile", key="profile:user:u1") is not None
