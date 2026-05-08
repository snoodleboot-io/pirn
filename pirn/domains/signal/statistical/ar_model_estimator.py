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
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _burg(x: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """Burg's recursive lattice method for AR coefficient estimation."""
    n = len(x)
    ef = x.astype(float).copy()
    eb = x.astype(float).copy()
    a = np.zeros(order)
    variance = float(np.dot(x, x) / n)
    for k in range(order):
        num = -2.0 * np.dot(eb[k : n - 1], ef[k + 1 : n])
        denom = np.dot(ef[k + 1 : n], ef[k + 1 : n]) + np.dot(eb[k : n - 1], eb[k : n - 1])
        km = 0.0 if denom == 0.0 else num / denom
        ef_new = ef[k + 1 : n] + km * eb[k : n - 1]
        eb_new = eb[k : n - 1] + km * ef[k + 1 : n]
        ef[k + 1 : n] = ef_new
        eb[k : n - 1] = eb_new
        a_new = np.zeros(k + 1)
        a_new[k] = km
        if k > 0:
            a_new[:k] = a[:k] + km * a[:k][::-1]
        a = a_new
        variance = variance * (1.0 - km * km)
    return a, float(variance)


def _compute_ar(x: np.ndarray, order: int, method: str) -> tuple[list[float], float]:
    """Dispatch AR estimation to the selected method and return (coefficients, variance)."""
    if method == "burg":
        coeffs, var = _burg(x, order)
        return list(float(c) for c in coeffs), var

    if method == "yule_walker":
        lpc_coeffs = ss.lpc(x, order)
        # ss.lpc returns [1, a1, a2, ...]; negate to get AR coefficients
        ar_coeffs = [-float(c) for c in lpc_coeffs[1:]]
        residual = x.copy()
        for i in range(order, len(x)):
            pred = sum(ar_coeffs[k] * x[i - k - 1] for k in range(order))
            residual[i] = x[i] - pred
        var = float(np.var(residual[order:]))
        return ar_coeffs, var

    # ols
    n = len(x)
    lag_matrix = np.column_stack([x[order - k - 1 : n - k - 1] for k in range(order)])
    target = x[order:]
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
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        coeffs, var = await asyncio.to_thread(_compute_ar, x, order, method)
        return {
            "coefficients": coeffs,
            "order": order,
            "method": method,
            "variance": var,
        }
