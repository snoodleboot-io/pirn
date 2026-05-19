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


def _prony(signal_array: np.ndarray, num_modes: int) -> tuple[list[complex], list[complex]]:
    """Prony's method: fit num_modes complex exponentials to signal_array.

    Returns (poles, residues).
    """
    signal_length = len(signal_array)
    # Build data matrix for linear prediction
    half = min(2 * num_modes, signal_length - 1)
    cols = min(num_modes, half)
    rows = half - cols
    if rows <= 0 or cols <= 0:
        return [], []
    data_matrix = np.array(
        [[signal_array[row_idx + col_idx] for col_idx in range(cols)] for row_idx in range(rows)]
    )
    target_vector = np.array([-signal_array[row_idx + cols] for row_idx in range(rows)])
    pred_coeffs, _, _, _ = np.linalg.lstsq(data_matrix, target_vector, rcond=None)
    # Characteristic polynomial: z^num_modes + a[0]*z^(num_modes-1) + ... + a[num_modes-1]
    poly = np.concatenate([[1.0], pred_coeffs])
    poles = np.roots(poly)
    # Vandermonde system to find residues
    n_pts = min(signal_length, 2 * num_modes)
    vandermonde = np.array(
        [[pole**sample_index for pole in poles] for sample_index in range(n_pts)]
    )
    residues, _, _, _ = np.linalg.lstsq(vandermonde, signal_array[:n_pts], rcond=None)
    return list(complex(pole) for pole in poles), list(complex(residue) for residue in residues)


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
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        poles, residues = await asyncio.to_thread(
            _prony, signal_array.astype(float), component_count
        )
        return {
            "poles": [str(p) for p in poles],
            "residues": [str(r) for r in residues],
            "model_order": component_count,
        }
