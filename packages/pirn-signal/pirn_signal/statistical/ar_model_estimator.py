"""``ARModelEstimator`` — fit an autoregressive model to a signal.

Algorithm:
    1. Receive the input signal frame, order, and method.
    2. Validate order (positive integer) and method (one of ``burg``, ``yule_walker``, ``ols``).
    3. Apply the selected estimation method:
       - ``burg``: Burg's recursive lattice method (minimum forward-backward error).
       - ``yule_walker``: Solve the Yule-Walker equations via the Levinson-Durbin recursion.
       - ``ols``: Ordinary least-squares regression on the lag matrix.
    4. Report every method in one sign convention: the AR coefficients
       ``phi_1 .. phi_p`` of ``x(n) = sum_k phi_k x(n-k) + e(n)``, followed by the
       innovation variance.
    5. Repeat independently for each channel and return a FeaturePayload with
       the AR coefficients and residual variance per channel.

Math:
    AR(p) model, as reported (``ar_coeff_{k-1}`` is :math:`\\phi_k`):

    $$x(n) = \\sum_{k=1}^{p} \\phi_k x(n-k) + e(n), \\qquad \\phi_k = -a_k$$

    where :math:`a` is the prediction polynomial
    :math:`A(z) = 1 + \\sum_k a_k z^{-k}` the Burg and Levinson-Durbin recursions
    operate on.

    Yule-Walker equations:

    $$\\mathbf{R} \\boldsymbol{\\phi} = \\mathbf{r}$$

    where $R_{ij} = R_x(i-j)$ and $r_i = R_x(i)$.

    Burg reflection coefficient at stage :math:`m` over forward errors :math:`f` and
    delayed backward errors :math:`b`, and the Levinson order update:

    $$k_m = \\frac{-2 \\sum_n f_{m-1}(n)\\, b_{m-1}(n-1)}
                 {\\sum_n f_{m-1}(n)^2 + \\sum_n b_{m-1}(n-1)^2}, \\qquad
      a^{(m)}_i = a^{(m-1)}_i + k_m\\, a^{(m-1)}_{m-i}, \\quad a^{(m)}_m = k_m$$

    $$\\sigma_m^2 = \\sigma_{m-1}^2 (1 - k_m^2)$$

References:
    - Burg, J.P. (1975). "Maximum Entropy Spectral Analysis." PhD thesis, Stanford University.
    - Kay, S.M. (1988). "Modern Spectral Estimation." Prentice-Hall, sec. 7.6 (Burg), 7.3
      (Yule-Walker / Levinson-Durbin).
    - Box, G.E.P., Jenkins, G.M. & Reinsel, G.C. (2015). "Time Series Analysis." Wiley.
    - MATLAB ``arburg`` (reference implementation of the same recursion):
      https://www.mathworks.com/help/signal/ref/arburg.html
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class ARModelEstimator(Knot):
    """Fit an autoregressive (AR) model to a signal using a configurable estimation method."""

    _valid_methods: ClassVar[frozenset[str]] = frozenset({"burg", "yule_walker", "ols"})

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
    ) -> FeaturePayload:
        """Fit an AR model and return the estimated parameters.

        Args:
            signal: The input signal payload.
            order: AR model order (positive integer).
            method: Estimation method — ``burg``, ``yule_walker``, or ``ols``.

        Returns:
            FeaturePayload with the AR coefficients (``ar_coeff_0`` .. ``ar_coeff_{order-1}``)
            and residual ``variance`` per channel.

        Raises:
            ValueError: If order or method are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ARModelEstimator: order must be a positive integer")
        if method not in self._valid_methods:
            raise ValueError("ARModelEstimator: method must be one of 'burg', 'yule_walker', 'ols'")
        channels = np.atleast_2d(signal.data)
        results = await asyncio.gather(
            *(
                asyncio.to_thread(ARModelEstimator._compute_ar, channel, order, method)
                for channel in channels
            )
        )
        rows = [[*coeffs, var] for coeffs, var in results]
        feature_names = (*(f"ar_coeff_{i}" for i in range(order)), "variance")
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:ar-{method}",
                channel_count=channels.shape[0],
                feature_names=feature_names,
            ),
            data=np.asarray(rows).reshape(channels.shape[0], order + 1),
        )

    @staticmethod
    def _burg(signal_array: np.ndarray, order: int) -> tuple[np.ndarray, float]:
        """Burg's lattice method; returns ``(phi, innovation variance)``.

        The recursion runs on the prediction polynomial ``a`` of
        ``x(n) + sum_k a_k x(n-k) = e(n)`` (Kay 1988, sec. 7.6; MATLAB ``arburg``):
        at stage ``m`` the forward errors ``f = f[1:]`` and the one-sample-delayed
        backward errors ``b = b[:-1]`` both shrink by one sample, the reflection
        coefficient is ``k = -2 <f, b> / (<f, f> + <b, b>)``, and
        ``a <- [a, 0] + k [0, reversed(a)]``. The AR coefficients are ``phi = -a``,
        the convention ``yule_walker`` and ``ols`` report.
        """
        forward = signal_array.astype(float).copy()
        backward = signal_array.astype(float).copy()
        polynomial = np.zeros(order)
        variance = float(np.dot(forward, forward) / forward.size)
        for stage in range(order):
            forward_errors = forward[1:]
            backward_errors = backward[:-1]
            denominator = float(
                np.dot(forward_errors, forward_errors) + np.dot(backward_errors, backward_errors)
            )
            reflection = (
                0.0
                if denominator == 0.0
                else -2.0 * float(np.dot(forward_errors, backward_errors)) / denominator
            )
            forward = forward_errors + reflection * backward_errors
            backward = backward_errors + reflection * forward_errors
            previous = polynomial[:stage].copy()
            polynomial[:stage] = previous + reflection * previous[::-1]
            polynomial[stage] = reflection
            variance *= 1.0 - reflection * reflection
        return -polynomial, variance

    @staticmethod
    def _levinson_durbin(signal_array: np.ndarray, order: int) -> np.ndarray:
        """Solve the Yule-Walker equations by the Levinson-Durbin recursion.

        Returns the prediction polynomial ``[1, a_1, ..., a_order]`` in the
        ``x(n) + sum_k a_k x(n-k) = e(n)`` convention (the same layout
        ``librosa.lpc`` uses). Uses the biased sample autocorrelation.
        """
        samples = signal_array.astype(float)
        signal_length = len(samples)
        autocorr = np.array(
            [
                float(np.dot(samples[: signal_length - lag], samples[lag:]))
                for lag in range(order + 1)
            ]
        )
        poly = np.zeros(order + 1)
        poly[0] = 1.0
        error = float(autocorr[0])
        for stage in range(1, order + 1):
            if error <= 0.0:
                break
            # sum_{j=0}^{stage-1} a_j r(stage - j)
            acc = float(np.dot(poly[:stage], autocorr[stage:0:-1]))
            reflection = -acc / error
            previous = poly.copy()
            for lag_idx in range(1, stage + 1):
                poly[lag_idx] = previous[lag_idx] + reflection * previous[stage - lag_idx]
            error *= 1.0 - reflection * reflection
        return poly

    @staticmethod
    def _compute_ar(signal_array: np.ndarray, order: int, method: str) -> tuple[list[float], float]:
        """Dispatch AR estimation to the selected method and return (coefficients, variance)."""
        if method == "burg":
            coeffs, var = ARModelEstimator._burg(signal_array, order)
            return list(float(c) for c in coeffs), var

        if method == "yule_walker":
            lpc_coeffs = ARModelEstimator._levinson_durbin(signal_array, order)
            # The prediction polynomial is [1, a1, a2, ...]; negate to get AR coefficients
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
