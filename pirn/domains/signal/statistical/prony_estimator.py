"""``PronyEstimator`` — fit damped sinusoids via Prony's method.

Algorithm:
    1. Receive the input signal frame and component_count.
    2. Validate component_count (positive integer).
    3. Form the data matrix from 2 * component_count signal samples.
    4. Solve the linear prediction problem to find the characteristic polynomial.
    5. Find the polynomial roots to obtain the complex modal frequencies (poles).
    6. Solve the Vandermonde system to obtain modal amplitudes.
    7. Return a mapping with the estimated modes and parameters.

Math:
    Prony model:

    $$x(n) = \\sum_{k=1}^{p} A_k z_k^n, \\quad z_k = e^{(\\sigma_k + j\\omega_k) T_s}$$

    Characteristic polynomial:

    $$a(z) = \\prod_{k=1}^{p} (1 - z_k z^{-1})$$

References:
    - Prony, G.R.B. (1795). "Essai expérimental et analytique." J. Éc. Polytech., 1(2), 24-76.
    - Kay, S.M. (1988). "Modern Spectral Estimation." Prentice-Hall.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _prony(x: np.ndarray, p: int) -> tuple[list[complex], list[complex]]:
    """Prony's method: fit p complex exponentials to x.

    Returns (poles, residues).
    """
    n = len(x)
    # Build data matrix for linear prediction
    half = min(2 * p, n - 1)
    cols = min(p, half)
    rows = half - cols
    if rows <= 0 or cols <= 0:
        return [], []
    X = np.array([[x[i + j] for j in range(cols)] for i in range(rows)])
    b = np.array([-x[i + cols] for i in range(rows)])
    coeffs, _, _, _ = np.linalg.lstsq(X, b, rcond=None)
    # Characteristic polynomial: z^p + a[0]*z^(p-1) + ... + a[p-1]
    poly = np.concatenate([[1.0], coeffs])
    poles = np.roots(poly)
    # Vandermonde system to find residues
    n_pts = min(n, 2 * p)
    V = np.array([[pole**k for pole in poles] for k in range(n_pts)])
    residues, _, _, _ = np.linalg.lstsq(V, x[:n_pts], rcond=None)
    return list(complex(z) for z in poles), list(complex(r) for r in residues)


class PronyEstimator(Knot):
    """Estimate damped exponential modes via Prony's method."""

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            component_count=component_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        component_count: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Fit damped sinusoidal modes to the signal via Prony's method and return a parameter mapping.

        Args:
            signal: Signal payload to decompose into damped exponential modes.
            component_count: Number of damped exponential modes to fit (positive integer).

        Returns:
            Mapping containing ``poles``, ``residues``, and ``model_order``.

        Raises:
            ValueError: If component_count is not a positive integer.
        """
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError("PronyEstimator: component_count must be a positive integer")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        poles, residues = await asyncio.to_thread(_prony, x.astype(float), component_count)
        return {
            "poles": [str(p) for p in poles],
            "residues": [str(r) for r in residues],
            "model_order": component_count,
        }
