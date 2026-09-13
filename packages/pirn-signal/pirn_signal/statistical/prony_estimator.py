"""``PronyEstimator`` — fit damped sinusoids via Prony's method.

Algorithm:
    1. Receive the input signal frame and component_count.
    2. Validate component_count (positive integer).
    3. Form the data matrix from 2 * component_count signal samples.
    4. Solve the linear prediction problem to find the characteristic polynomial.
    5. Find the polynomial roots to obtain the complex modal frequencies (poles).
    6. Solve the Vandermonde system to obtain modal amplitudes.
    7. Repeat independently for each channel and return a FeaturePayload whose
       data is shaped ``(channel_count, component_count, 2)``, pairing each
       mode's complex pole and residue (NaN-padded when fewer modes are found).

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
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


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
    ) -> FeaturePayload:
        """Fit damped sinusoidal modes to the signal via Prony's method.

        Args:
            signal: Signal payload to decompose into damped exponential modes.
            component_count: Number of damped exponential modes to fit (positive integer).

        Returns:
            FeaturePayload with complex ``data`` shaped
            ``(channel_count, component_count, 2)``: for each channel, up to
            ``component_count`` ``(pole, residue)`` pairs, NaN-padded when
            fewer modes are found.

        Raises:
            ValueError: If component_count is not a positive integer.
        """
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError("PronyEstimator: component_count must be a positive integer")
        channels = np.atleast_2d(signal.data).astype(float)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(PronyEstimator._prony, channel, component_count)
                for channel in channels
            )
        )
        pad_value = complex(float("nan"), float("nan"))
        rows = []
        for poles, residues in results:
            padded_poles = poles + [pad_value] * (component_count - len(poles))
            padded_residues = residues + [pad_value] * (component_count - len(residues))
            rows.append(list(zip(padded_poles, padded_residues, strict=True)))
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:prony",
                channel_count=channels.shape[0],
                feature_names=("pole", "residue"),
            ),
            data=np.asarray(rows, dtype=complex).reshape(channels.shape[0], component_count, 2),
        )

    @staticmethod
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
            [
                [signal_array[row_idx + col_idx] for col_idx in range(cols)]
                for row_idx in range(rows)
            ]
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
