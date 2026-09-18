"""Synthetic signals with known analytic answers, for reference tests.

Every generator here produces a signal whose generating parameters are the
ground truth an estimator must recover:

* :meth:`ReferenceSignals.fractional_gaussian_noise` — exact fractional Gaussian
  noise of a chosen Hurst exponent, by the Davies-Harte circulant-embedding method
  (Davies, R.B. & Harte, D.S. (1987). "Tests for Hurst effect." Biometrika 74(1),
  95-101; Dietrich, C.R. & Newsam, G.N. (1997). SIAM J. Sci. Comput. 18(4), 1088-1107).
* :meth:`ReferenceSignals.autoregressive` — an AR(p) process
  ``x(n) = sum_k phi_k x(n-k) + e(n)`` with known ``phi`` and innovation variance.
* :meth:`ReferenceSignals.damped_exponentials` — ``x(n) = sum_k A_k z_k^n``, the
  exact model Prony's method fits.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


class ReferenceSignals:
    """Generators for signals whose parameters are known exactly."""

    @staticmethod
    def fractional_gaussian_noise(hurst: float, length: int, seed: int) -> NDArray[np.float64]:
        """Exact unit-variance fGn of Hurst exponent ``hurst`` (Davies-Harte).

        The autocovariance of fGn is
        ``gamma(k) = 0.5 (|k+1|^{2H} - 2|k|^{2H} + |k-1|^{2H})``. Its circulant
        embedding of size ``m = 2 length`` has non-negative eigenvalues for every
        ``H`` in (0, 1), so the spectral synthesis below is exact.
        """
        lags = np.arange(length + 1, dtype=float)
        exponent = 2.0 * hurst
        gamma = 0.5 * (
            np.abs(lags + 1) ** exponent
            - 2.0 * np.abs(lags) ** exponent
            + np.abs(lags - 1) ** exponent
        )
        embedding = np.concatenate([gamma, gamma[-2:0:-1]])
        size = embedding.size
        eigenvalues = np.fft.fft(embedding).real
        if np.min(eigenvalues) < -1e-9:
            raise ValueError("Davies-Harte embedding is not non-negative definite")
        eigenvalues = np.clip(eigenvalues, 0.0, None)
        rng = np.random.default_rng(seed)
        weights = np.sqrt(eigenvalues / size) * (
            rng.standard_normal(size) + 1j * rng.standard_normal(size)
        )
        return np.fft.fft(weights).real[:length]

    @staticmethod
    def autoregressive(
        phi: tuple[float, ...], length: int, seed: int, sigma: float = 1.0, burn_in: int = 1000
    ) -> NDArray[np.float64]:
        """AR(p) realisation ``x(n) = sum_k phi_k x(n-k) + sigma e(n)``, ``e ~ N(0, 1)``."""
        rng = np.random.default_rng(seed)
        order = len(phi)
        total = length + burn_in
        innovations = sigma * rng.standard_normal(total)
        samples = np.zeros(total)
        for index in range(total):
            history = sum(
                phi[lag] * samples[index - lag - 1] for lag in range(order) if index - lag - 1 >= 0
            )
            samples[index] = history + innovations[index]
        return samples[burn_in:]

    @staticmethod
    def damped_exponentials(
        poles: tuple[complex, ...], amplitudes: tuple[complex, ...], length: int
    ) -> NDArray[Any]:
        """``x(n) = sum_k A_k z_k^n`` for ``n = 0 .. length-1``."""
        sample_index = np.arange(length)
        return sum(
            (
                amplitude * pole**sample_index
                for pole, amplitude in zip(poles, amplitudes, strict=True)
            ),
            start=np.zeros(length, dtype=complex),
        )
