"""``PisarenkoEstimator`` — Pisarenko harmonic decomposition.

Algorithm:
    1. Receive the input signal frame and sinusoid_count.
    2. Validate sinusoid_count (positive integer).
    3. Compute the autocorrelation matrix R of order (sinusoid_count + 1).
    4. Find the minimum eigenvector of R (corresponding to the noise subspace).
    5. Solve for sinusoid frequencies as the roots of the minimum eigenvector polynomial.
    6. Return a mapping with estimated frequencies and parameters.

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
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _pisarenko(x: np.ndarray, p: int, sample_rate_hz: float) -> list[float]:
    """Estimate p sinusoid frequencies via Pisarenko harmonic decomposition."""
    n = len(x)
    size = p + 1
    # Build Toeplitz autocorrelation matrix
    r = np.array([np.dot(x[: n - k], x[k:]) / n for k in range(size)])
    R = np.array([[r[abs(i - j)] for j in range(size)] for i in range(size)])
    eigenvalues, eigenvectors = np.linalg.eigh(R)
    # Minimum eigenvalue corresponds to noise subspace
    min_idx = int(np.argmin(eigenvalues))
    noise_vec = eigenvectors[:, min_idx]
    # Roots of the polynomial defined by the noise vector
    roots = np.roots(noise_vec)
    # Keep roots on or near unit circle
    on_circle = roots[np.abs(np.abs(roots) - 1.0) < 0.3]
    # Frequencies from angles of roots
    freqs = sorted(
        float(np.angle(r) / (2.0 * np.pi) * sample_rate_hz) for r in on_circle if np.angle(r) > 0
    )
    return freqs[:p]


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
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies via Pisarenko harmonic decomposition and return a parameter mapping.

        Args:
            signal: Signal payload to estimate harmonic frequencies from.
            sinusoid_count: Number of sinusoidal components to identify (positive integer).

        Returns:
            Mapping containing ``frequencies_hz``, ``sample_rate_hz``, and ``num_sinusoids``.

        Raises:
            ValueError: If sinusoid_count is not a positive integer.
        """
        if not isinstance(sinusoid_count, int) or sinusoid_count <= 0:
            raise ValueError("PisarenkoEstimator: sinusoid_count must be a positive integer")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        rate = signal.frame.sample_rate_hz
        freqs = await asyncio.to_thread(_pisarenko, x, sinusoid_count, rate)
        return {
            "frequencies_hz": freqs,
            "sample_rate_hz": rate,
            "num_sinusoids": sinusoid_count,
        }
