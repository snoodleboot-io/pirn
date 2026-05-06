"""``SourceLocalizer`` — localise neural sources from sensor signals.

Production version uses MNE / dSPM / sLORETA / beamformer. This stub
validates inputs and returns an empty mapping ``source -> activation``.

Algorithm:
    1. Receive a SignalFrame, method string, and source_labels sequence.
    2. Validate types and that method is one of mne/dspm/sloreta/beamformer.
    3. Apply the inverse solution to map sensor signals to source space.
    4. Return a mapping of source label to estimated activation.


References:
    - MNE inverse solutions: https://mne.tools/stable/auto_tutorials/inverse/
    - Pascual-Marqui (2002) Standardized Low-Resolution Brain Electromagnetic Tomography (sLORETA).
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
        signal: Knot | SignalFrame,
        method: Knot | str,
        source_labels: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            method=method,
            source_labels=source_labels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        method: str,
        source_labels: Sequence[str],
        **_: Any,
    ) -> Mapping[str, float]:
        """Estimate source-space activations from the sensor signal and return a source-label-to-activation mapping.

        Args:
            signal: The sensor-space SignalFrame to invert.
            method: Inverse solution method; one of 'mne', 'dspm', 'sloreta', 'beamformer'.
            source_labels: Sequence of source region label strings.

        Returns:
            A mapping from source label to estimated activation value.

        Raises:
            TypeError: If signal is not SignalFrame or source_labels is not list/tuple of strings.
            ValueError: If method is not a valid inverse method.
        """
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
        return {label: 0.0 for label in source_labels}
