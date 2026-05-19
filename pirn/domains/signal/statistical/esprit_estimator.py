"""``ESPRITEstimator`` — rotational-invariance subspace frequency estimator.

Algorithm:
    1. Receive the input signal frame and signal_subspace_dim.
    2. Validate signal_subspace_dim (positive integer).
    3. Compute the autocorrelation matrix of the signal.
    4. Compute the eigendecomposition and partition into signal and noise subspaces.
    5. Solve the ESPRIT rotational invariance equation to obtain frequency estimates.
    6. Return a mapping with the estimated frequencies and parameters.

Math:
    Signal subspace partition:

    $$\\mathbf{R} = \\mathbf{E}_s \\mathbf{\\Lambda}_s \\mathbf{E}_s^H + \\sigma^2 \\mathbf{E}_n \\mathbf{E}_n^H$$

    ESPRIT equation:

    $$\\mathbf{E}_{s1}^\\dagger \\mathbf{E}_{s2} = \\mathbf{\\Phi}$$

    where $e^{j\\omega_k}$ are the eigenvalues of $\\mathbf{\\Phi}$.

References:
    - Roy, R. & Kailath, T. (1989). "ESPRIT — Estimation of signal parameters via rotational invariance
      techniques." IEEE Trans. Acoust. Speech Signal Process., 37(7), 984-995.
    - numpy.linalg: https://numpy.org/doc/stable/reference/routines.linalg.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _esprit(signal_array: np.ndarray, num_sinusoids: int, sample_rate_hz: float) -> list[float]:
    """Estimate num_sinusoids sinusoid frequencies via ESPRIT."""
    signal_length = len(signal_array)
    size = num_sinusoids + 1
    autocorr = np.array(
        [
            np.dot(signal_array[: signal_length - lag], signal_array[lag:]) / signal_length
            for lag in range(size)
        ]
    )
    autocorr_matrix = np.array(
        [[autocorr[abs(row_idx - col_idx)] for col_idx in range(size)] for row_idx in range(size)]
    )
    _, eigenvectors = np.linalg.eigh(autocorr_matrix)
    # Signal subspace: num_sinusoids eigenvectors with largest eigenvalues
    signal_vecs = eigenvectors[:, size - num_sinusoids :]
    # Partition into upper (Es1) and lower (Es2) submatrices
    Es1 = signal_vecs[:-1, :]
    Es2 = signal_vecs[1:, :]
    # Solve least-squares: Es1 @ Phi = Es2
    Phi, _, _, _ = np.linalg.lstsq(Es1, Es2, rcond=None)
    eigs = np.linalg.eigvals(Phi)
    angles = np.angle(eigs)
    freqs = sorted(float(ang / (2.0 * np.pi) * sample_rate_hz) for ang in angles if ang > 0)
    return freqs[:num_sinusoids]


class ESPRITEstimator(Knot):
    """ESPRIT high-resolution sinusoid estimator."""

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            signal_subspace_dim=signal_subspace_dim,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        signal_subspace_dim: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies from the signal via ESPRIT and return a parameter mapping.

        Args:
            signal: Signal payload to estimate frequencies from.
            signal_subspace_dim: Dimension of the signal subspace (positive integer).

        Returns:
            Mapping containing ``frequencies_hz``, ``sample_rate_hz``, and ``num_sinusoids``.

        Raises:
            ValueError: If signal_subspace_dim is not a positive integer.
        """
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError("ESPRITEstimator: signal_subspace_dim must be a positive integer")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        rate = signal.frame.sample_rate_hz
        freqs = await asyncio.to_thread(_esprit, signal_array, signal_subspace_dim, rate)
        return {
            "frequencies_hz": freqs,
            "sample_rate_hz": rate,
            "num_sinusoids": signal_subspace_dim,
        }
