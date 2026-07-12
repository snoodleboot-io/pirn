"""``EntityProfile`` — durable, cross-session per-user/per-entity state.

A profile aggregates what the agent has learned about one subject across many
sessions: a free-form ``fields`` mapping (preferences, attributes, …), the
:class:`~pirn_agents.memory_management.memory_provenance.MemoryProvenance` of its
last update, and the set of ``session_ids`` that have contributed. It is a frozen
value object that round-trips through the untyped
:class:`~pirn_agents.memory_store.MemoryStore` mapping interface via
:meth:`to_payload` / :meth:`from_payload`, so a profile persists and is re-read
with no store-side schema.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_provenance import MemoryProvenance
from pirn_agents.memory_management.profile_key import ProfileKey


@dataclass(frozen=True)
class EntityProfile(PirnOpaqueValue):
    """A subject's aggregated, cross-session profile.

    Attributes
    ----------
    key:
        The subject-scoped :class:`ProfileKey`.
    fields:
        Merged attribute mapping accumulated across sessions.
    provenance:
        Origin + trust metadata of the most recent update.
    updated_at:
        Timezone-aware time of the most recent update.
    session_ids:
        The ordered, de-duplicated ids of sessions that have contributed.
    """

    key: ProfileKey
    fields: Mapping[str, Any]
    provenance: MemoryProvenance
    updated_at: datetime
    session_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.key, ProfileKey):
            raise TypeError(
                f"EntityProfile: key must be a ProfileKey, got {type(self.key).__name__}"
            )
        if not isinstance(self.fields, Mapping):
            raise TypeError("EntityProfile: fields must be a Mapping")
        if not isinstance(self.provenance, MemoryProvenance):
            raise TypeError("EntityProfile: provenance must be a MemoryProvenance")
        if not isinstance(self.updated_at, datetime):
            raise TypeError("EntityProfile: updated_at must be a datetime")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        return {
            "namespace": self.key.namespace,
            "subject_id": self.key.subject_id,
            "fields": dict(self.fields),
            "provenance": self.provenance.to_payload(),
            "updated_at": self.updated_at.isoformat(),
            "session_ids": list(self.session_ids),
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
        if not isinstance(payload, Mapping):
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
