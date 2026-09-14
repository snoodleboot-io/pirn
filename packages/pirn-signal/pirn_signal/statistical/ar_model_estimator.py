"""``ARModelEstimator`` — fit an autoregressive model to a signal.

Algorithm:
    1. Receive the input signal frame, order, and method.
    2. Validate order (positive integer) and method (one of ``burg``, ``yule_walker``, ``ols``).
    3. Apply the selected estimation method:
       - ``burg``: Burg's recursive lattice method (minimum forward-backward error).
       - ``yule_walker``: Solve the Yule-Walker equations via the Levinson-Durbin recursion.
       - ``ols``: Ordinary least-squares regression on the lag matrix.
    4. Repeat independently for each channel and return a FeaturePayload with
       the AR coefficients and residual variance per channel.

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
                signal_id=f"{signal.frame.signal_id}:ar-{method}",
                channel_count=channels.shape[0],
                feature_names=feature_names,
            ),
            data=np.asarray(rows).reshape(channels.shape[0], order + 1),
        )

    @staticmethod
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
            ef_new = (
                ef[lattice_stage + 1 : signal_length] + km * eb[lattice_stage : signal_length - 1]
            )
            eb_new = (
                eb[lattice_stage : signal_length - 1] + km * ef[lattice_stage + 1 : signal_length]
            )
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
