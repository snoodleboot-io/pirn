"""``SignalFrame`` — generic multi-channel signal frame.

Used by EEG/MEG and wearable knots once a recording is loaded. The frame
is a logical handle, not the underlying ndarray (which lives in the
production-only path).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SignalFrame(PirnOpaqueValue):
    """Logical pointer to a multi-channel signal frame."""

    signal_id: str = ""
    channel_count: int = 0
    sample_rate_hz: float = 0.0
    samples_per_channel: int = 0
    fetched_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "channel_count": self.channel_count,
            "sample_rate_hz": self.sample_rate_hz,
            "samples_per_channel": self.samples_per_channel,
            "fetched_at": self.fetched_at.isoformat(),
        }
