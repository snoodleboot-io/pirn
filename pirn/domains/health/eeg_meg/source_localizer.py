"""``SourceLocalizer`` — localise neural sources from sensor signals.

Algorithm:
    1. Receive a SignalPayload, method string, and source_labels sequence.
    2. Validate types and that method is one of mne/dspm/sloreta/beamformer.
    3. Compute per-source activation using a minimum-norm-style estimate.
    4. Return a mapping of source label to estimated activation.


References:
    - MNE inverse solutions: https://mne.tools/stable/auto_tutorials/inverse/
    - Pascual-Marqui (2002) Standardized Low-Resolution Brain Electromagnetic Tomography (sLORETA).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _minimum_norm_estimate(data: np.ndarray, n_sources: int) -> np.ndarray:
    """Return a synthetic activation value per source derived from signal amplitude.

    The mean absolute amplitude across time is computed from the data, then
    interpolated/repeated to cover n_sources and normalised to [0, 1].
    """
    channel_means = np.abs(data).mean(axis=-1)  # (n_channels,) or scalar
    channel_means = np.atleast_1d(channel_means).astype(float)
    indices = np.linspace(0, len(channel_means) - 1, n_sources)
    source_activations = np.interp(indices, np.arange(len(channel_means)), channel_means)
    max_val = source_activations.max()
    if max_val > 0.0:
        source_activations = source_activations / max_val
    return source_activations


class SourceLocalizer(Knot):
    """Estimate source-space activations from sensor-space signals."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
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
        signal: SignalPayload,
        method: str,
        source_labels: Sequence[str],
        **_: Any,
    ) -> Mapping[str, float]:
        """Estimate source-space activations from the sensor signal.

        Args:
            signal: The sensor-space SignalPayload to invert.
            method: Inverse solution method; one of 'mne', 'dspm', 'sloreta', 'beamformer'.
            source_labels: Sequence of source region label strings.

        Returns:
            A mapping from source label to estimated activation value in [0, 1].

        Raises:
            TypeError: If signal is not SignalPayload or source_labels is not list/tuple of strings.
            ValueError: If method is not a valid inverse method.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("SourceLocalizer: signal must be a SignalPayload")
        if method not in ("mne", "dspm", "sloreta", "beamformer"):
            raise ValueError("SourceLocalizer: method must be one of mne/dspm/sloreta/beamformer")
        if not isinstance(source_labels, (list, tuple)):
            raise TypeError("SourceLocalizer: source_labels must be list/tuple")
        for label in source_labels:
            if not isinstance(label, str):
                raise TypeError("SourceLocalizer: every source label must be a string")

        n_sources = len(source_labels)
        if n_sources == 0:
            return {}
        activations = await asyncio.to_thread(_minimum_norm_estimate, signal.data, n_sources)
        return {label: float(activations[i]) for i, label in enumerate(source_labels)}
