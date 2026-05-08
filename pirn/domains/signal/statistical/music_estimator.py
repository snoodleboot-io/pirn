"""``MUSICEstimator`` — high-resolution sinusoid frequency estimation.

Algorithm:
    1. Receive the input signal frame, signal_subspace_dim, and frequency_grid_size.
    2. Validate signal_subspace_dim and frequency_grid_size (positive integers).
    3. Compute the autocorrelation matrix and its eigendecomposition.
    4. Partition eigenvectors into signal subspace (top signal_subspace_dim) and noise subspace.
    5. Evaluate the MUSIC pseudo-spectrum over a grid of frequency_grid_size points:
       P_MUSIC(f) = 1 / ‖E_n^H a(f)‖².
    6. Find peaks in the pseudo-spectrum to estimate the sinusoid frequencies.
    7. Return a mapping with the estimated frequencies and parameters.

Math:
    MUSIC pseudo-spectrum:

    $$P_{\\text{MUSIC}}(f) = \\frac{1}{\\mathbf{a}^H(f) \\mathbf{E}_n \\mathbf{E}_n^H \\mathbf{a}(f)}$$

    where $\\mathbf{a}(f)$ = steering vector and $\\mathbf{E}_n$ = noise subspace.

References:
    - Schmidt, R.O. (1986). "Multiple emitter location and signal parameter estimation."
      IEEE Trans. Antennas Propag., 34(3), 276-280.
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


def _music_pseudospectrum(
    x: np.ndarray, p: int, n_freq: int, sample_rate_hz: float
) -> tuple[list[float], list[float]]:
    """Compute MUSIC pseudospectrum and return (pseudospectrum, frequencies_hz)."""
    n = len(x)
    size = p + 1
    r = np.array([np.dot(x[: n - k], x[k:]) / n for k in range(size)])
    R = np.array([[r[abs(i - j)] for j in range(size)] for i in range(size)])
    _, eigenvectors = np.linalg.eigh(R)
    # Noise subspace: eigenvectors corresponding to smallest (size - p) eigenvalues
    # eigh returns ascending order; noise subspace is all except the p largest
    noise_vecs = eigenvectors[:, : size - p]
    En = noise_vecs @ noise_vecs.conj().T
    freqs_hz = np.linspace(0.0, sample_rate_hz / 2.0, n_freq)
    pseudo = np.zeros(n_freq)
    for i, f in enumerate(freqs_hz):
        a = np.exp(1j * 2.0 * np.pi * f * np.arange(size) / sample_rate_hz)
        denom = float(np.real(a.conj() @ En @ a))
        pseudo[i] = 1.0 / denom if denom != 0.0 else np.inf
    return list(float(v) for v in pseudo), list(float(f) for f in freqs_hz)


class MUSICEstimator(Knot):
    """MUltiple SIgnal Classification frequency estimator."""

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: Knot | int,
        frequency_grid_size: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            signal_subspace_dim=signal_subspace_dim,
            frequency_grid_size=frequency_grid_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        signal_subspace_dim: int,
        frequency_grid_size: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies from the signal via MUSIC and return a parameter mapping.

        Args:
            signal: Signal payload to estimate frequencies from.
            signal_subspace_dim: Dimension of the signal subspace (positive integer).
            frequency_grid_size: Number of frequency grid points in the pseudo-spectrum (positive integer).

        Returns:
            Mapping containing ``pseudospectrum``, ``frequencies_hz``, and ``num_sinusoids``.

        Raises:
            ValueError: If signal_subspace_dim or frequency_grid_size are not positive integers.
        """
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError("MUSICEstimator: signal_subspace_dim must be a positive integer")
        if not isinstance(frequency_grid_size, int) or frequency_grid_size <= 0:
            raise ValueError("MUSICEstimator: frequency_grid_size must be a positive integer")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        rate = signal.frame.sample_rate_hz
        pseudo, freqs = await asyncio.to_thread(
            _music_pseudospectrum, x, signal_subspace_dim, frequency_grid_size, rate
        )
        return {
            "pseudospectrum": pseudo,
            "frequencies_hz": freqs,
            "num_sinusoids": signal_subspace_dim,
        }
