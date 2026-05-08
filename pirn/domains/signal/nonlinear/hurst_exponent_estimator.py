"""``HurstExponentEstimator`` — long-range dependence / fractal estimator.

Algorithm:
    1. Receive the input signal frame and method.
    2. Validate method (one of ``rs``, ``dfa``, ``wavelet``).
    3. Apply the selected estimation method:
       - ``rs``: Rescaled-range (R/S) analysis over partitions of increasing length.
       - ``dfa``: Detrended fluctuation analysis with linear detrending.
       - ``wavelet``: Wavelet-based LRD estimator from spectral slope.
    4. Fit the log-log slope to obtain the Hurst exponent H ∈ (0, 1).
    5. Return a result mapping with the estimated exponent and method.

Math:
    Rescaled-range scaling:

    $$E\\left[\\frac{R(n)}{S(n)}\\right] \\sim C \\cdot n^H \\quad \\text{as } n \\to \\infty$$

    where $R(n)$ is the range and $S(n)$ is the standard deviation over $n$ observations.

References:
    - Hurst, H.E. (1951). "Long-term storage capacity of reservoirs." Trans. Am. Soc. Civil Eng., 116, 770-808.
    - nolds library: https://github.com/CSchoel/nolds
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _hurst_rs(x: np.ndarray) -> float:
    """Hurst exponent via R/S analysis over partitions of increasing length."""
    n = len(x)
    min_len = 10
    max_len = n // 2
    if max_len <= min_len:
        return 0.5
    lengths = np.unique(np.logspace(np.log10(min_len), np.log10(max_len), 20).astype(int))
    rs_vals = []
    for length in lengths:
        n_segments = n // length
        if n_segments == 0:
            continue
        rs_seg = []
        for i in range(n_segments):
            seg = x[i * length : (i + 1) * length].astype(float)
            seg_mean = np.mean(seg)
            deviation = np.cumsum(seg - seg_mean)
            r = float(np.max(deviation) - np.min(deviation))
            s = float(np.std(seg, ddof=1))
            if s > 0:
                rs_seg.append(r / s)
        if rs_seg:
            rs_vals.append((float(length), float(np.mean(rs_seg))))
    if len(rs_vals) < 2:
        return 0.5
    log_n = np.array([np.log(v[0]) for v in rs_vals])
    log_rs = np.array([np.log(v[1]) for v in rs_vals])
    coeffs = np.polyfit(log_n, log_rs, 1)
    return float(np.clip(coeffs[0], 0.0, 1.0))


def _hurst_dfa(x: np.ndarray) -> float:
    """Hurst exponent via detrended fluctuation analysis."""
    n = len(x)
    profile = np.cumsum(x - np.mean(x))
    min_len = 10
    max_len = n // 4
    if max_len <= min_len:
        return 0.5
    lengths = np.unique(np.logspace(np.log10(min_len), np.log10(max_len), 20).astype(int))
    fluct = []
    for length in lengths:
        n_seg = n // length
        if n_seg == 0:
            continue
        f2 = []
        for i in range(n_seg):
            seg = profile[i * length : (i + 1) * length]
            idx = np.arange(length)
            p = np.polyfit(idx, seg, 1)
            trend = np.polyval(p, idx)
            f2.append(np.mean((seg - trend) ** 2))
        fluct.append((float(length), float(np.sqrt(np.mean(f2)))))
    if len(fluct) < 2:
        return 0.5
    log_n = np.array([np.log(v[0]) for v in fluct])
    log_f = np.array([np.log(v[1]) for v in fluct])
    coeffs = np.polyfit(log_n, log_f, 1)
    return float(np.clip(coeffs[0], 0.0, 1.0))


def _hurst_wavelet(x: np.ndarray) -> float:
    """Hurst exponent via wavelet energy scaling."""
    n = len(x)
    max_level = int(np.log2(n)) - 1
    if max_level < 2:
        return 0.5
    energies = []
    sig = x.astype(float)
    for level in range(1, max_level + 1):
        # Simple Haar wavelet detail coefficients
        half = len(sig) // 2
        if half == 0:
            break
        detail = sig[: 2 * half : 2] - sig[1 : 2 * half : 2]
        energies.append((float(level), float(np.log(np.mean(detail**2) + 1e-12))))
        sig = (sig[: 2 * half : 2] + sig[1 : 2 * half : 2]) / 2.0
    if len(energies) < 2:
        return 0.5
    levels = np.array([e[0] for e in energies])
    log_e = np.array([e[1] for e in energies])
    coeffs = np.polyfit(levels, log_e, 1)
    # Relationship: slope ~ -(2H + 1)
    h = float(-(coeffs[0] + 1) / 2.0)
    return float(np.clip(h, 0.0, 1.0))


def _compute_hurst(x: np.ndarray, method: str) -> float:
    """Dispatch Hurst exponent computation to the selected method."""
    if method == "rs":
        return _hurst_rs(x)
    if method == "dfa":
        return _hurst_dfa(x)
    return _hurst_wavelet(x)


class HurstExponentEstimator(Knot):
    """Estimate the Hurst exponent (long-memory / self-similarity)."""

    _valid_methods = frozenset({"rs", "dfa", "wavelet"})

    def __init__(
        self,
        *,
        signal: Knot,
        method: Knot | str = "rs",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        method: str = "rs",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the Hurst exponent of the signal using the configured method.

        Args:
            signal: Signal payload to estimate long-range dependence from.
            method: Estimation method — ``rs`` (rescaled range), ``dfa``
                (detrended fluctuation analysis), or ``wavelet``.

        Returns:
            Mapping containing ``hurst_exponent`` and ``signal_id``.

        Raises:
            ValueError: If method is not one of the valid options.
        """
        if method not in self._valid_methods:
            raise ValueError("HurstExponentEstimator: method must be 'rs', 'dfa', or 'wavelet'")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        h = await asyncio.to_thread(_compute_hurst, x.astype(float), method)
        return {
            "hurst_exponent": h,
            "signal_id": signal.frame.signal_id,
        }
