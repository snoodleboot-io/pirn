"""``SignalPayload`` — time-domain signal metadata bundled with its sample array.

Returned by knots that produce or transform time-domain signal data.
``metadata`` carries the lineage metadata; ``data`` is the sample array,
shaped ``(channels, samples)`` for multi-channel signals or ``(samples,)``
for mono.  Both fields travel together through the transport layer so
downstream knots receive the full picture in one input.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pirn.core.payload import Payload

from pirn_signal.types.signal_frame import SignalFrame


class SignalPayload(Payload[SignalFrame, np.ndarray]):
    """Time-domain signal: metadata frame + sample array."""

    def derive(self, tag: str, data: np.ndarray, **frame_overrides: Any) -> SignalPayload:
        """Build a new :class:`SignalPayload` derived from this one.

        Inherits ``channel_count`` and ``sample_rate_hz`` from this payload's
        frame, tags ``signal_id`` with ``:{tag}``, and computes
        ``samples_per_channel`` from ``data``'s trailing axis. Any of these
        may be overridden via ``frame_overrides`` for knots whose output
        changes channel count, sample rate, or is not shaped ``(..., samples)``.

        Args:
            tag: Suffix appended to this payload's ``signal_id`` as ``:{tag}``.
            data: The new sample array to carry in the derived payload.
            **frame_overrides: Overrides for any :class:`SignalFrame` field
                (typically ``channel_count`` or ``sample_rate_hz``).

        Returns:
            A new ``SignalPayload`` with the derived frame and ``data``.
        """
        fields: dict[str, Any] = {
            "signal_id": f"{self.metadata.signal_id}:{tag}",
            "channel_count": self.metadata.channel_count,
            "sample_rate_hz": self.metadata.sample_rate_hz,
            "samples_per_channel": data.shape[-1],
        }
        fields.update(frame_overrides)
        return SignalPayload(metadata=SignalFrame(**fields), data=data)
