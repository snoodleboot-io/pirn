"""``EntityProfileFrame`` — the lineage half of an :class:`EntityProfile` (PIR-868, PIR-874)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.profile_key import ProfileKey


@dataclass(frozen=True)
class EntityProfileFrame(PirnOpaqueValue):
    """Who a profile is about, where its last update came from, and who contributed.

    Attributes
    ----------
    key:
        The subject-scoped :class:`ProfileKey`.
    provenance:
        Origin + trust metadata of the most recent update.
    updated_at:
        Timezone-aware time of the most recent update.
    session_ids:
        The ordered, de-duplicated ids of sessions that have contributed.
    """

    key: ProfileKey
    provenance: MemoryProvenance
    updated_at: datetime
    session_ids: tuple[str, ...] = field(default_factory=tuple)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.key.namespace,
            "subject_id": self.key.subject_id,
            "provenance": self.provenance.to_payload(),
            "updated_at": self.updated_at.isoformat(),
            "session_ids": list(self.session_ids),
        }
