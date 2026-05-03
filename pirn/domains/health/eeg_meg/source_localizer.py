"""``SourceLocalizer`` — localise neural sources from sensor signals.

Production version uses MNE / dSPM / sLORETA / beamformer. This stub
validates inputs and returns an empty mapping ``source -> activation``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class SourceLocalizer(Knot):
    """Estimate source-space activations from sensor-space signals."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        method: str,
        source_labels: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "SourceLocalizer: signal must be a SignalFrame"
            )
        if method not in ("mne", "dspm", "sloreta", "beamformer"):
            raise ValueError(
                "SourceLocalizer: method must be one of mne/dspm/sloreta/beamformer"
            )
        if not isinstance(source_labels, (list, tuple)):
            raise TypeError(
                "SourceLocalizer: source_labels must be list/tuple"
            )
        for label in source_labels:
            if not isinstance(label, str):
                raise TypeError(
                    "SourceLocalizer: every source label must be a string"
                )
        self._signal = signal
        self._method = method
        self._source_labels = tuple(source_labels)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        """Estimate source-space activations from the sensor signal and return a source-label-to-activation mapping.

        Returns:
            A mapping from source label to estimated activation value.
        """
        return {label: 0.0 for label in self._source_labels}
