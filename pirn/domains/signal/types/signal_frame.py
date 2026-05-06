"""``SignalFrame`` — typed reference to a captured digital signal.

The frame does not embed sample arrays; it carries the metadata
downstream knots need to load samples on demand. The intent mirrors
:class:`pirn.domains.ml.types.ml_dataset.MLDataset`: a small lineage
record, not a heavy buffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SignalFrame(PirnOpaqueValue):
    """Reference to a digital signal captured by an ingestor."""

    signal_id: str = ""
    channel_count: int = 0
    sample_rate_hz: float = 0.0
    samples_per_channel: int = 0
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "channel_count": self.channel_count,
            "sample_rate_hz": self.sample_rate_hz,
            "samples_per_channel": self.samples_per_channel,
            "fetched_at": self.fetched_at.isoformat(),
        }
