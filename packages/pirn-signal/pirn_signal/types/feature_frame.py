"""``FeatureFrame`` — typed reference to a named scalar/vector feature set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class FeatureFrame(PirnOpaqueValue):
    """Reference to a set of named features extracted from a signal.

    ``feature_names`` enumerates the feature columns present in the
    companion :class:`~pirn_signal.types.feature_payload.FeaturePayload`'s
    ``data``, which is shaped ``(channel_count, len(feature_names))``.
    """

    signal_id: str = ""
    channel_count: int = 0
    feature_names: tuple[str, ...] = ()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "channel_count": self.channel_count,
            "feature_names": list(self.feature_names),
        }
