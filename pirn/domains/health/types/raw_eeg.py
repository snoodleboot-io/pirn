"""``RawEEG`` — raw multi-channel EEG recording snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
            "subject_id": self.subject_id,
            "channel_count": self.channel_count,
            "sample_rate_hz": self.sample_rate_hz,
            "duration_sec": self.duration_sec,
            "fetched_at": self.fetched_at.isoformat(),
        }
