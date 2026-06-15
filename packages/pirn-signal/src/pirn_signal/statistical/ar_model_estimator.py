"""``ARModelEstimator`` — fit an autoregressive model to a signal.

Algorithm:
    1. Receive the input signal frame, order, and method.
    2. Validate order (positive integer) and method (one of ``burg``, ``yule_walker``, ``ols``).
    3. Apply the selected estimation method:
       - ``burg``: Burg's recursive lattice method (minimum forward-backward error).
       - ``yule_walker``: Solve the Yule-Walker equations via the Levinson-Durbin recursion.
       - ``ols``: Ordinary least-squares regression on the lag matrix.
    4. Return the estimated AR coefficients, model order, method, and residual variance.

Math:
    AR(p) model:

    $$x(n) = -\\sum_{k=1}^{p} a_k x(n-k) + e(n)$$

    Yule-Walker equations:

    $$\\mathbf{R} \\mathbf{a} = -\\mathbf{r}$$

    where $R_{ij} = R_x(i-j)$ and $r_i = R_x(i)$.

References:
    - Box, G.E.P., Jenkins, G.M. & Reinsel, G.C. (2015). "Time Series Analysis." Wiley.
    - scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy import signal as ss

from pirn_signal.types.signal_payload import SignalPayload


def _burg(signal_array: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """Burg's recursive lattice method for AR coefficient estimation."""
    signal_length = len(signal_array)
    ef = signal_array.astype(float).copy()
    eb = signal_array.astype(float).copy()
    ar_coeffs = np.zeros(order)
    variance = float(np.dot(signal_array, signal_array) / signal_length)
    for lattice_stage in range(order):
        num = -2.0 * np.dot(
            eb[lattice_stage : signal_length - 1], ef[lattice_stage + 1 : signal_length]
        )
        denom = np.dot(
            ef[lattice_stage + 1 : signal_length], ef[lattice_stage + 1 : signal_length]
        ) + np.dot(eb[lattice_stage : signal_length - 1], eb[lattice_stage : signal_length - 1])
        km = 0.0 if denom == 0.0 else num / denom
        ef_new = ef[lattice_stage + 1 : signal_length] + km * eb[lattice_stage : signal_length - 1]
        eb_new = eb[lattice_stage : signal_length - 1] + km * ef[lattice_stage + 1 : signal_length]
        ef[lattice_stage + 1 : signal_length] = ef_new
        eb[lattice_stage : signal_length - 1] = eb_new
        coeffs_new = np.zeros(lattice_stage + 1)
        coeffs_new[lattice_stage] = km
        if lattice_stage > 0:
            coeffs_new[:lattice_stage] = (
                ar_coeffs[:lattice_stage] + km * ar_coeffs[:lattice_stage][::-1]
            )
        ar_coeffs = coeffs_new
        variance = variance * (1.0 - km * km)
    return ar_coeffs, float(variance)


def _compute_ar(signal_array: np.ndarray, order: int, method: str) -> tuple[list[float], float]:
    """Dispatch AR estimation to the selected method and return (coefficients, variance)."""
    if method == "burg":
        coeffs, var = _burg(signal_array, order)
        return list(float(c) for c in coeffs), var

    if method == "yule_walker":
        lpc_coeffs = ss.lpc(signal_array, order)
        # ss.lpc returns [1, a1, a2, ...]; negate to get AR coefficients
        ar_coeffs = [-float(c) for c in lpc_coeffs[1:]]
        residual = signal_array.copy()
        for sample_idx in range(order, len(signal_array)):
            pred = sum(
                ar_coeffs[lag_idx] * signal_array[sample_idx - lag_idx - 1]
                for lag_idx in range(order)
            )
            residual[sample_idx] = signal_array[sample_idx] - pred
        var = float(np.var(residual[order:]))
        return ar_coeffs, var

    # ols
    signal_length = len(signal_array)
    lag_matrix = np.column_stack(
        [
            signal_array[order - lag_idx - 1 : signal_length - lag_idx - 1]
            for lag_idx in range(order)
        ]
    )
    target = signal_array[order:]
    result, _, _, _ = np.linalg.lstsq(lag_matrix, target, rcond=None)
    ar_coeffs = [float(c) for c in result]
    pred = lag_matrix @ result
    var = float(np.var(target - pred))
    return ar_coeffs, var


class ARModelEstimator(Knot):
    """Fit an autoregressive (AR) model to a signal using a configurable estimation method."""

    _valid_methods = frozenset({"burg", "yule_walker", "ols"})

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        order: int,
        method: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Fit an AR model and return the estimated parameters.

        Args:
            signal: The input signal payload.
            order: AR model order (positive integer).
            method: Estimation method — ``burg``, ``yule_walker``, or ``ols``.

        Returns:
            Dict with keys ``coefficients`` (list[float]), ``order`` (int),
            ``method`` (str), and ``variance`` (float).

        Raises:
            ValueError: If order or method are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ARModelEstimator: order must be a positive integer")
        if method not in self._valid_methods:
            raise ValueError("ARModelEstimator: method must be one of 'burg', 'yule_walker', 'ols'")
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        coeffs, var = await asyncio.to_thread(_compute_ar, signal_array, order, method)
        return {
            "coefficients": coeffs,
            "order": order,
            "method": method,
            "variance": var,
        }
