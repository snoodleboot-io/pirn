"""``PronyEstimator`` — fit damped sinusoids via Prony's method.

Algorithm:
    1. Receive the input signal frame and component_count.
    2. Validate component_count (positive integer).
    3. Form the least-squares linear-prediction system over every sample:
       row ``r`` is ``[x(r), ..., x(r+p-1)]`` and its target is ``-x(r+p)``, for
       ``r = 0 .. N-p-1`` (fewer than ``2p`` samples yields no modes).
    4. Solve it for the prediction coefficients ``c_0 .. c_{p-1}``.
    5. Take the roots of the characteristic polynomial
       ``z^p + c_{p-1} z^{p-1} + ... + c_0`` (coefficients highest power first) as
       the modal poles ``z_k``.
    6. Solve the Vandermonde system ``x(n) = sum_k A_k z_k^n`` by least squares for
       the residues ``A_k``, over every sample whose powers ``z_k^n`` stay finite.
    7. Repeat independently for each channel and return a FeaturePayload whose
       data is shaped ``(channel_count, component_count, 2)``, pairing each
       mode's complex pole and residue (NaN-padded when fewer modes are found).

Math:
    Prony model:

    $$x(n) = \\sum_{k=1}^{p} A_k z_k^n, \\quad z_k = e^{(\\sigma_k + j\\omega_k) T_s}$$

    Every such signal obeys the order-:math:`p` linear recurrence

    $$x(n + p) + \\sum_{i=0}^{p-1} c_i\\, x(n + i) = 0$$

    whose characteristic polynomial has exactly the poles as roots:

    $$z^p + \\sum_{i=0}^{p-1} c_i z^i = \\prod_{k=1}^{p} (z - z_k)$$

References:
    - Prony, G.R.B. (1795). "Essai expérimental et analytique." J. Éc. Polytech., 1(2), 24-76.
    - Kay, S.M. (1988). "Modern Spectral Estimation." Prentice-Hall, sec. 11.3
      (least-squares Prony method).
    - Hildebrand, F.B. (1956). "Introduction to Numerical Analysis." McGraw-Hill, sec. 9.4.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from numpy.typing import NDArray
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
        rows: list[list[tuple[complex, complex]]] = []
        for poles, residues in results:
            padded_poles = poles + [pad_value] * (component_count - len(poles))
            padded_residues = residues + [pad_value] * (component_count - len(residues))
            rows.append(list(zip(padded_poles, padded_residues, strict=True)))
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:prony",
                channel_count=channels.shape[0],
                feature_names=("pole", "residue"),
            ),
            data=np.asarray(rows, dtype=complex).reshape(channels.shape[0], component_count, 2),
        )

    @staticmethod
    def _prony(signal_array: np.ndarray, num_modes: int) -> tuple[list[complex], list[complex]]:
        """Least-squares Prony: fit ``num_modes`` complex exponentials to ``signal_array``.

        Returns ``(poles, residues)``; both are empty when the signal has fewer than
        ``2 * num_modes`` samples (the linear-prediction system is underdetermined).
        """
        signal_length = len(signal_array)
        rows = signal_length - num_modes
        if rows < num_modes:
            return [], []
        # Linear prediction over every available sample: row r is
        # [x(r), x(r+1), ..., x(r+p-1)] and the target is -x(r+p), so the solution
        # c satisfies x(r+p) + sum_i c_i x(r+i) = 0.
        data_matrix = np.lib.stride_tricks.sliding_window_view(signal_array[:-1], num_modes)[:rows]
        target_vector = -signal_array[num_modes:]
        pred_coeffs, _, _, _ = np.linalg.lstsq(data_matrix, target_vector, rcond=None)
        # That recurrence's characteristic polynomial is
        # z^p + c_{p-1} z^{p-1} + ... + c_1 z + c_0: highest power first for np.roots,
        # so the solved coefficients go in reverse order.
        poly = np.concatenate([[1.0], pred_coeffs[::-1]])
        # np.roots is typed as real-or-complex; a real-rooted polynomial still has
        # complex poles as far as the residue fit is concerned, so hold one dtype.
        poles: NDArray[np.complexfloating[Any, Any]] = np.asarray(
            np.roots(poly), dtype=np.complex128
        )
        # Residues: least squares on the Vandermonde system over every sample whose
        # power z^n stays finite (a pole outside the unit circle grows geometrically).
        fit_length = PronyEstimator._finite_power_length(poles, signal_length)
        vandermonde = np.power.outer(poles, np.arange(fit_length)).T
        residues, _, _, _ = np.linalg.lstsq(vandermonde, signal_array[:fit_length], rcond=None)
        return [complex(pole) for pole in poles], [complex(residue) for residue in residues]

    @staticmethod
    def _finite_power_length(poles: NDArray[np.complexfloating[Any]], signal_length: int) -> int:
        """Largest sample count ``n <= signal_length`` with every ``|z_k|^n`` below ``1e150``."""
        largest = float(np.max(np.abs(poles))) if poles.size else 0.0
        if largest <= 1.0:
            return signal_length
        return max(poles.size, min(signal_length, int(150.0 * np.log(10.0) / np.log(largest))))
