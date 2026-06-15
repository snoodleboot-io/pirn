"""``MEGBeamformer`` — spatial filter (LCMV beamformer) for MEG source localization.

Algorithm:
    1. Receive signal HealthSignalPayload and steering_vector list[float].
    2. Validate types and dimensions.
    3. Compute the data covariance matrix R = (data @ data.T) / n_samples.
    4. Compute MVDR weight vector w = R^{-1} @ sv / (sv.T @ R^{-1} @ sv).
    5. Compute beamformed output = w.T @ data.
    6. Return beamformed_power (mean squared output) and weight_vector.

Math:
    $$\\mathbf{W}_k = \\frac{\\mathbf{C}^{-1}\\mathbf{l}_k}{\\mathbf{l}_k^T\\mathbf{C}^{-1}\\mathbf{l}_k}$$

References:
    - Van Veen et al. (1997) Localization of brain electrical activity via LCMV beamforming.
    - MNE beamformer: https://mne.tools/stable/auto_tutorials/inverse/50_beamformer_lcmv.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.health_signal_payload import HealthSignalPayload


def _lcmv_beamform(data: np.ndarray, sv: np.ndarray) -> tuple[float, np.ndarray]:
    """Compute LCMV beamformer weights and beamformed power.

    Args:
        data: Signal array of shape (n_channels, n_samples).
        sv: Steering vector of shape (n_channels,).

    Returns:
        Tuple of (beamformed_power, weight_vector).
    """
    n_samples = data.shape[1]
    cov = (data @ data.T) / n_samples  # (n_channels, n_channels)
    cov_inv = np.linalg.pinv(cov)
    numerator = cov_inv @ sv
    denominator = sv @ cov_inv @ sv
    weights = numerator / (denominator + 1e-12)
    beamformed = weights @ data  # (n_samples,)
    power = float(np.mean(beamformed**2))
    return power, weights


class MEGBeamformer(Knot):
    """Spatial filter (LCMV beamformer) for MEG source localization."""

    def __init__(
        self,
        *,
        signal: Knot | HealthSignalPayload,
        steering_vector: Knot | list[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            steering_vector=steering_vector,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: HealthSignalPayload,
        steering_vector: list[float],
        **_: Any,
    ) -> dict[str, Any]:
        """Apply LCMV beamformer to the signal and return power and weight vector.

        Args:
            signal: The HealthSignalPayload containing MEG sensor data (channels x samples).
            steering_vector: Lead-field vector of length n_channels pointing at the source.

        Returns:
            Dict with beamformed_power (float) and weight_vector (list of float).

        Raises:
            TypeError: If signal is not HealthSignalPayload or steering_vector is not list.
            ValueError: If steering_vector length does not match signal channel count.
        """
        if not isinstance(signal, HealthSignalPayload):
            raise TypeError("MEGBeamformer: signal must be a HealthSignalPayload")
        if not isinstance(steering_vector, list):
            raise TypeError("MEGBeamformer: steering_vector must be a list of float")
        n_channels = signal.frame.channel_count
        if len(steering_vector) != n_channels:
            raise ValueError(
                f"MEGBeamformer: steering_vector length {len(steering_vector)} "
                f"does not match channel_count {n_channels}"
            )
        data = signal.data.reshape(n_channels, -1).astype(float)
        sv = np.array(steering_vector, dtype=float)
        power, weights = await asyncio.to_thread(_lcmv_beamform, data, sv)
        return {
            "beamformed_power": power,
            "weight_vector": weights.tolist(),
        }
