"""``RawEEG`` — raw multi-channel EEG recording snapshot.

PHI safety:
    ``subject_id`` never appears in :meth:`_pirn_audit_dict` — see
    :mod:`pirn_health.types.genomics_record` for the rule. The audit dict
    carries ``subject_id_hash``, a stable
    :class:`~pirn.core.content_hasher.ContentHasher` digest that keeps two
    subjects' recordings distinct in lineage without persisting the
    identifier itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RawEEG(PirnOpaqueValue):
    """Reference to a raw EEG recording (channels x samples)."""

    subject_id: str = ""
    channel_count: int = 0
    sample_rate_hz: float = 0.0
    duration_sec: float = 0.0
    fetched_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "subject_id_hash": ContentHasher.hash(self.subject_id),
            "channel_count": self.channel_count,
            "sample_rate_hz": self.sample_rate_hz,
            "duration_sec": self.duration_sec,
            "fetched_at": self.fetched_at.isoformat(),
        }
