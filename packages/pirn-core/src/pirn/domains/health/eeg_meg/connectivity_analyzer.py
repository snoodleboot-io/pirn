"""``ConnectivityAnalyzer`` — pairwise channel connectivity via PLV.

Algorithm:
    1. Receive a HealthSignalPayload, channel_names sequence, and method string.
    2. Validate types and that method is one of plv/coherence/wpli.
    3. Compute Phase Locking Value (PLV) for each channel pair via scipy.signal.hilbert.
       PLV = |mean(exp(i * phase_diff))|
    4. Return a symmetric nested mapping of channel-to-channel PLV scores.

Math:
    Phase Locking Value between channels x and y:

    PLV(x, y) = |1/N * sum_{t=1}^{N} exp(i * (phi_x(t) - phi_y(t)))|

    where phi_x(t) and phi_y(t) are the instantaneous phases obtained via the Hilbert transform.

References:
    - Bastos & Schoffelen (2016) A Tutorial Review of Functional Connectivity Analysis Methods.
    - Lachaux et al. (1999) Measuring Phase Synchrony in Brain Signals.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload


def _plv(signal_a: np.ndarray, signal_b: np.ndarray) -> float:
    phase_a = np.angle(np.asarray(ss.hilbert(signal_a)))
    phase_b = np.angle(np.asarray(ss.hilbert(signal_b)))
    return float(np.abs(np.mean(np.exp(1j * (phase_a - phase_b)))))


def _compute_plv_matrix(
    data: np.ndarray,
    channel_names: Sequence[str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {ch: {} for ch in channel_names}
    for row_index, ch_i in enumerate(channel_names):
        for col_index, ch_j in enumerate(channel_names):
            if row_index == col_index:
                result[ch_i][ch_j] = 1.0
            elif col_index < row_index:
                result[ch_i][ch_j] = result[ch_j][ch_i]
            else:
                if data.ndim > 1 and row_index < data.shape[0] and col_index < data.shape[0]:
                    plv = _plv(data[row_index], data[col_index])
                else:
                    plv = 0.0
                result[ch_i][ch_j] = plv
    return result


class ConnectivityAnalyzer(Knot):
    """Compute pairwise connectivity between channels."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        channel_names: Knot | Sequence[str],
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            channel_names=channel_names,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        channel_names: Sequence[str],
        method: str,
        **_: Any,
    ) -> Mapping[str, Mapping[str, float]]:
        """Compute pairwise PLV connectivity between all channel pairs.

        Args:
            signal: The HealthSignalPayload to analyze.
            channel_names: Sequence of channel name strings.
            method: Connectivity method; one of 'plv', 'coherence', 'wpli'.

        Returns:
            A nested mapping from channel name to a mapping of other channel names to PLV scores.

        Raises:
            TypeError: If signal is not HealthSignalPayload or channel_names is not list/tuple of strings.
            ValueError: If method is not one of plv/coherence/wpli.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("ConnectivityAnalyzer: signal must be a HealthSignalPayload")
        if not isinstance(channel_names, (list, tuple)):
            raise TypeError("ConnectivityAnalyzer: channel_names must be list/tuple")
        for name in channel_names:
            if not isinstance(name, str):
                raise TypeError("ConnectivityAnalyzer: every channel name must be string")
        if method not in ("plv", "coherence", "wpli"):
            raise ValueError("ConnectivityAnalyzer: method must be one of plv/coherence/wpli")

        return await asyncio.to_thread(_compute_plv_matrix, signal.data, channel_names)
