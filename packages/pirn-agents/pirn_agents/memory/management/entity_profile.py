"""``EntityProfile`` — durable, cross-session per-user/per-entity state.

A profile aggregates what the agent has learned about one subject across many
sessions: a free-form ``fields`` mapping (preferences, attributes, …), the
:class:`~pirn_agents.memory.management.memory_provenance.MemoryProvenance` of its
last update, and the set of ``session_ids`` that have contributed. It is a frozen
value object that round-trips through the untyped
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` mapping interface via
:meth:`to_payload` / :meth:`from_payload`, so a profile persists and is re-read
with no store-side schema.

``EntityProfile`` is ``Payload[EntityProfileFrame, Mapping[str, Any]]`` (PIR-868
pattern, enforced by PIR-874): the frame carries ``key``/``provenance``/
``updated_at``/``session_ids`` and ``data`` is the merged ``fields`` mapping. It
subclasses :class:`pirn.core.payload.Payload` directly, like ``MemoryRecord``,
because ``memory/`` must not import from ``specializations/``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.core.payload import Payload

from pirn_agents._internal.json_shape import JsonShape
from pirn_agents.memory.management.entity_profile_frame import EntityProfileFrame
from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.profile_key import ProfileKey


class EntityProfile(Payload[EntityProfileFrame, Mapping[str, Any]]):
    """A subject's aggregated, cross-session profile.

    The constructor takes ``key`` (the subject-scoped :class:`ProfileKey`),
    ``fields`` (merged attribute mapping accumulated across sessions),
    ``provenance`` (origin + trust of the most recent update), ``updated_at``
    (timezone-aware time of the most recent update) and ``session_ids`` (ordered,
    de-duplicated contributing session ids). Read back as ``metadata.<field>``
    and ``data`` (the ``fields`` mapping).
    """

    def __init__(
        self,
        key: ProfileKey,
        fields: Mapping[str, Any],
        provenance: MemoryProvenance,
        updated_at: datetime,
        session_ids: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(key, ProfileKey):
            raise TypeError(f"EntityProfile: key must be a ProfileKey, got {type(key).__name__}")
        if not JsonShape.is_mapping(fields):
            raise TypeError("EntityProfile: fields must be a Mapping")
        if not isinstance(provenance, MemoryProvenance):
            raise TypeError("EntityProfile: provenance must be a MemoryProvenance")
        if not isinstance(updated_at, datetime):
            raise TypeError("EntityProfile: updated_at must be a datetime")
        frame = EntityProfileFrame(
            key=key,
            provenance=provenance,
            updated_at=updated_at,
            session_ids=tuple(session_ids),
        )
        super().__init__(metadata=frame, data=fields)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        return {
            "namespace": self.metadata.key.namespace,
            "subject_id": self.metadata.key.subject_id,
            "fields": dict(self.data),
            "provenance": self.metadata.provenance.to_payload(),
            "updated_at": self.metadata.updated_at.isoformat(),
            "session_ids": list(self.metadata.session_ids),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> EntityProfile:
        """Reconstruct a profile from a mapping produced by :meth:`to_payload`.

        Args:
            payload: A mapping with ``namespace``/``subject_id``/``fields``/
                ``provenance``/``updated_at`` and optional ``session_ids``.

        Returns:
            The reconstructed :class:`EntityProfile`.

        Raises:
            TypeError: If ``payload`` is not a mapping.
        """
        if not JsonShape.is_mapping(payload):
            raise TypeError(
                f"EntityProfile.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw_sessions: Sequence[Any] = payload.get("session_ids", ())
        return cls(
            key=ProfileKey(
                namespace=payload["namespace"],
                subject_id=str(payload["subject_id"]),
            ),
            fields=dict(payload.get("fields", {})),
            provenance=MemoryProvenance.from_payload(payload["provenance"]),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            session_ids=tuple(str(sid) for sid in raw_sessions),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityProfile):
            return NotImplemented
        return self.metadata == other.metadata and self.data == other.data
