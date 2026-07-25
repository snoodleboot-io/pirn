"""``CrossSessionProfileUpdater`` — load, merge, and persist a subject profile.

The S3 profile knot. In one ``process`` pass it reads the existing profile for a
:class:`~pirn_agents.memory_management.profile_key.ProfileKey` through the standard
:meth:`~pirn_agents.memory_store.MemoryStore.retrieve` interface, folds in the new
session's fields with
:func:`~pirn_agents.memory_management.profile_merge.merge_profile_fields` (so
unrelated existing fields are never clobbered), records the contributing session
id, refreshes provenance, and writes the merged
:class:`~pirn_agents.memory_management.entity_profile.EntityProfile` back under the
subject-scoped :attr:`ProfileKey.storage_key`. Because that key is
session-independent, the profile persists and accumulates across sessions — the
point where **F14** durable sessions will later supply the session identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.entity_profile import EntityProfile
from pirn_agents.memory_management.memory_provenance import MemoryProvenance
from pirn_agents.memory_management.profile_key import ProfileKey
from pirn_agents.memory_management.profile_merge import merge_profile_fields
from pirn_agents.memory_store import MemoryStore


class CrossSessionProfileUpdater(Knot):
    """Merges new session data into a persisted per-subject profile."""

    def __init__(
        self,
        *,
        key: Knot | ProfileKey,
        incoming_fields: Knot | Mapping[str, Any],
        store: Knot | MemoryStore,
        now: Knot | datetime,
        source: Knot | str = "profile_updater",
        trust_signal: Knot | float = 1.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            key=key,
            incoming_fields=incoming_fields,
            store=store,
            now=now,
            source=source,
            trust_signal=trust_signal,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        key: ProfileKey,
        incoming_fields: Mapping[str, Any],
        store: MemoryStore,
        now: datetime,
        source: str = "profile_updater",
        trust_signal: float = 1.0,
        **_: Any,
    ) -> EntityProfile:
        """Load, merge, persist, and return the updated profile for ``key``.

        Args:
            key: The subject-scoped profile key.
            incoming_fields: New session data to fold into the profile.
            store: The MemoryStore the profile is read from and written to.
            now: The timezone-aware update time.
            source: Provenance source label for this update.
            trust_signal: Provenance trust in ``[0, 1]`` for this update.

        Returns:
            The merged, persisted :class:`EntityProfile`.

        Raises:
            TypeError: If ``key`` is not a ProfileKey, ``incoming_fields`` is not
                a Mapping, ``store`` is not a MemoryStore, or ``now`` is not a
                datetime.
        """
        if not isinstance(key, ProfileKey):
            raise TypeError(
                f"CrossSessionProfileUpdater: key must be a ProfileKey, got {type(key).__name__}"
            )
        if not isinstance(incoming_fields, Mapping):
            raise TypeError("CrossSessionProfileUpdater: incoming_fields must be a Mapping")
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"CrossSessionProfileUpdater: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(now, datetime):
            raise TypeError("CrossSessionProfileUpdater: now must be a datetime")
        existing = await store.retrieve(key.storage_key)
        prior_fields, prior_sessions = self._prior_state(existing)
        merged_fields = merge_profile_fields(prior_fields, incoming_fields)
        session_ids = self._extend_sessions(prior_sessions, key.session_id)
        profile = EntityProfile(
            key=ProfileKey(namespace=key.namespace, subject_id=key.subject_id),
            fields=merged_fields,
            provenance=MemoryProvenance(source=source, timestamp=now, trust_signal=trust_signal),
            updated_at=now,
            session_ids=session_ids,
        )
        await store.store(key.storage_key, profile.to_payload())
        return profile

    @staticmethod
    def _prior_state(
        existing: Mapping[str, Any] | None,
    ) -> tuple[Mapping[str, Any], tuple[str, ...]]:
        """Return the prior ``(fields, session_ids)`` from a stored payload."""
        if existing is None:
            return {}, ()
        profile = EntityProfile.from_payload(existing)
        return profile.fields, profile.session_ids

    @staticmethod
    def _extend_sessions(prior: tuple[str, ...], session_id: str | None) -> tuple[str, ...]:
        """Append ``session_id`` to ``prior`` if new, preserving order."""
        if session_id is None or session_id in prior:
            return prior
        return (*prior, session_id)
