"""``PisarenkoEstimator`` — Pisarenko harmonic decomposition.

Algorithm:
    1. Receive the input signal frame and sinusoid_count.
    2. Validate sinusoid_count (positive integer).
    3. Compute the autocorrelation matrix R of order (sinusoid_count + 1).
    4. Find the minimum eigenvector of R (corresponding to the noise subspace).
    5. Solve for sinusoid frequencies as the roots of the minimum eigenvector polynomial.
    6. Repeat independently for each channel and return a FeaturePayload with
       the estimated frequencies per channel (NaN-padded when fewer than
       sinusoid_count frequencies are found).

Math:
    Minimum eigenvector decomposition:

    $$\\mathbf{R} \\mathbf{v}_{\\min} = \\sigma_n^2 \\mathbf{v}_{\\min}$$

    Frequency polynomial:

    $$V(z) = \\sum_{k=0}^{p} v_k z^{-k} = \\prod_{i=1}^{p} (1 - e^{j\\omega_i} z^{-1})$$

References:
    - Pisarenko, V.F. (1973). "The retrieval of harmonics from a covariance function."
      Geophys. J. R. Astron. Soc., 33(3), 347-366.
    - numpy.linalg: https://numpy.org/doc/stable/reference/routines.linalg.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class PisarenkoEstimator(Knot):
    """Pisarenko harmonic-decomposition frequency estimator."""

    def __init__(
        self,
        *,
        signal: Knot,
        sinusoid_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            sinusoid_count=sinusoid_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        sinusoid_count: int,
        **_: Any,
    ) -> FeaturePayload:
        """Estimate sinusoid frequencies via Pisarenko harmonic decomposition.

        Args:
            signal: Signal payload to estimate harmonic frequencies from.
            sinusoid_count: Number of sinusoidal components to identify (positive integer).

        Returns:
            FeaturePayload with up to ``sinusoid_count`` estimated frequencies (Hz)
            per channel, NaN-padded when fewer are found.

        Raises:
            ValueError: If sinusoid_count is not a positive integer.
        """
        if not isinstance(sinusoid_count, int) or sinusoid_count <= 0:
            raise ValueError("PisarenkoEstimator: sinusoid_count must be a positive integer")
        rate = signal.frame.sample_rate_hz
        channels = np.atleast_2d(signal.data)
        freqs = await asyncio.gather(
            *(
                asyncio.to_thread(PisarenkoEstimator._pisarenko, channel, sinusoid_count, rate)
                for channel in channels
            )
        )
        padded = [f + [float("nan")] * (sinusoid_count - len(f)) for f in freqs]
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:pisarenko",
                channel_count=channels.shape[0],
                feature_names=tuple(f"freq_{i}" for i in range(sinusoid_count)),
            ),
            data=np.asarray(padded).reshape(channels.shape[0], sinusoid_count),
        )

    @staticmethod
    def _pisarenko(
        signal_array: np.ndarray, num_sinusoids: int, sample_rate_hz: float
    ) -> list[float]:
        """Estimate num_sinusoids sinusoid frequencies via Pisarenko harmonic decomposition."""
        signal_length = len(signal_array)
        size = num_sinusoids + 1
        # Build Toeplitz autocorrelation matrix
        autocorr = np.array(
            [
                np.dot(signal_array[: signal_length - lag], signal_array[lag:]) / signal_length
                for lag in range(size)
            ]
        )
        autocorr_matrix = np.array(
            [
                [autocorr[abs(row_idx - col_idx)] for col_idx in range(size)]
                for row_idx in range(size)
            ]
        )
        eigenvalues, eigenvectors = np.linalg.eigh(autocorr_matrix)
        # Minimum eigenvalue corresponds to noise subspace
        min_idx = int(np.argmin(eigenvalues))
        noise_vec = eigenvectors[:, min_idx]
        # Roots of the polynomial defined by the noise vector
        roots = np.roots(noise_vec)
        # Keep roots on or near unit circle
        on_circle = roots[np.abs(np.abs(roots) - 1.0) < 0.3]
        # Frequencies from angles of roots
        freqs = sorted(
            float(np.angle(root) / (2.0 * np.pi) * sample_rate_hz)
            for root in on_circle
            if np.angle(root) > 0
        )
        return freqs[:num_sinusoids]
