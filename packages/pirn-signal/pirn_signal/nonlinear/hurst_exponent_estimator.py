"""``HurstExponentEstimator`` — long-range dependence / fractal estimator.

The input is treated as a stationary increment process (fractional Gaussian noise,
fGn, for a Gaussian signal); the estimate is the Hurst exponent ``H`` of that
process. A random walk (fractional Brownian motion) should be differenced first.

Algorithm:
    1. Receive the input signal frame and method.
    2. Validate method (one of ``rs``, ``dfa``, ``wavelet``).
    3. For each channel, reject a signal shorter than the method's minimum length
       or a constant signal with ``ValueError`` — neither has a Hurst exponent, and
       no default value is ever substituted.
    4. Apply the selected estimation method:
       - ``rs``: rescaled-range (R/S) analysis. For ~20 log-spaced window lengths
         ``n`` in ``[10, N/2]``, split the signal into non-overlapping windows, take
         the range of the mean-removed cumulative sum over the sample standard
         deviation in each, and average. ``H`` is the least-squares slope of
         ``ln E[R/S]`` against ``ln n``.
       - ``dfa``: detrended fluctuation analysis (order 1). Integrate the
         mean-removed signal into a profile, split it into windows of ~20
         log-spaced lengths ``n`` in ``[10, N/4]``, remove a least-squares line
         from each window and take the RMS residual ``F(n)``. ``H`` is the slope
         of ``ln F(n)`` against ``ln n``.
       - ``wavelet``: Abry-Veitch log-scale diagram on the orthonormal Haar
         transform. At each octave ``j`` with at least 16 detail coefficients,
         compute ``mu_j = mean(d_j^2)``, form ``y_j = log2 mu_j - g_j`` with the
         bias correction ``g_j``, and fit ``y_j`` against ``j`` by weighted least
         squares (weights ``n_j``, the coefficient counts). ``H = (slope + 1) / 2``.
    5. Report the fitted exponent unclipped: an estimate outside ``(0, 1)`` is a
       real finding (non-stationary input), not a value to round into range.
    6. Return a FeaturePayload with one Hurst exponent per channel.

Math:
    Rescaled-range and DFA scaling for fGn of exponent :math:`H`:

    $$E\\left[\\frac{R(n)}{S(n)}\\right] \\sim C_{RS} \\, n^H, \\qquad F(n) \\sim C_F \\, n^H$$

    Orthonormal Haar detail variance at octave :math:`j` for fGn:

    $$E[d_j^2] = C_W \\, 2^{j(2H - 1)}
      \\;\\Rightarrow\\; \\log_2 E[d_j^2] = (2H - 1)\\, j + \\log_2 C_W
      \\;\\Rightarrow\\; H = \\frac{\\text{slope} + 1}{2}$$

    Bias of the log of a sample mean of :math:`n_j` squared Gaussian coefficients
    (first-order expansion of :math:`\\psi(n_j/2)/\\ln 2 - \\log_2(n_j/2)`):

    $$g_j \\approx -\\frac{1}{n_j \\ln 2}$$

References:
    - Hurst, H.E. (1951). "Long-term storage capacity of reservoirs." Trans. Am. Soc.
      Civil Eng., 116, 770-808.
    - Anis, A.A. & Lloyd, E.H. (1976). "The expected value of the adjusted rescaled Hurst
      range of independent normal summands." Biometrika, 63(1), 111-116 (small-sample R/S
      bias; not corrected here).
    - Peng, C.-K. et al. (1994). "Mosaic organization of DNA nucleotides." Phys. Rev. E,
      49(2), 1685-1689 (DFA).
    - Abry, P. & Veitch, D. (1998). "Wavelet analysis of long-range-dependent traffic."
      IEEE Trans. Inf. Theory, 44(1), 2-15 (log-scale diagram, bias correction, weights).
    - Davies, R.B. & Harte, D.S. (1987). "Tests for Hurst effect." Biometrika, 74(1),
      95-101 (exact fGn synthesis used by the reference tests).
    - nolds library (alternative implementation of R/S and DFA):
      https://github.com/CSchoel/nolds
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class HurstExponentEstimator(Knot):
    """Estimate the Hurst exponent (long-memory / self-similarity)."""

    _valid_methods: ClassVar[frozenset[str]] = frozenset({"rs", "dfa", "wavelet"})
    _min_window: ClassVar[int] = 10
    _window_count: ClassVar[int] = 20
    _min_octave_coefficients: ClassVar[int] = 16
    # Shortest signal each method can fit a slope to: R/S and DFA need their largest
    # window (N/2 resp. N/4) above the 10-sample minimum; the wavelet method needs two
    # octaves with at least 16 detail coefficients each.
    _min_samples: ClassVar[Mapping[str, int]] = {"rs": 22, "dfa": 44, "wavelet": 64}

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
    ) -> FeaturePayload:
        """Estimate the Hurst exponent of the signal using the configured method.

        Args:
            signal: Signal payload to estimate long-range dependence from.
            method: Estimation method — ``rs`` (rescaled range), ``dfa``
                (detrended fluctuation analysis), or ``wavelet``.

        Returns:
            FeaturePayload with one ``hurst_exponent`` value per channel.

        Raises:
            ValueError: If method is not one of the valid options, or a channel is
                too short for the method or constant.
        """
        if method not in self._valid_methods:
            raise ValueError("HurstExponentEstimator: method must be 'rs', 'dfa', or 'wavelet'")
        channels = np.atleast_2d(signal.data).astype(float)
        values = await asyncio.gather(
            *(
                asyncio.to_thread(HurstExponentEstimator._compute_hurst, channel, method)
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:hurst-exponent",
                channel_count=channels.shape[0],
                feature_names=("hurst_exponent",),
            ),
            data=np.asarray(values).reshape(channels.shape[0], 1),
        )

    @staticmethod
    def _window_lengths(max_len: int) -> list[int]:
        """Distinct integer window lengths, log-spaced over ``[_min_window, max_len]``."""
        grid: NDArray[np.float64] = np.logspace(
            float(np.log10(HurstExponentEstimator._min_window)),
            float(np.log10(max_len)),
            HurstExponentEstimator._window_count,
        )
        return sorted({int(length) for length in grid})

    @staticmethod
    def _slope(
        x: NDArray[np.float64], y: NDArray[np.float64], weights: NDArray[np.float64] | None = None
    ) -> float:
        """Least-squares slope of ``y`` on ``x`` (weighted when ``weights`` are given)."""
        if x.size < 2:
            raise ValueError(
                "HurstExponentEstimator: fewer than two usable scales — the signal is too "
                "degenerate to fit a scaling slope"
            )
        coeffs = np.polyfit(x, y, 1, w=None if weights is None else np.sqrt(weights))
        return float(coeffs[0])

    @staticmethod
    def _hurst_rs(signal_array: NDArray[np.float64]) -> float:
        """Hurst exponent via R/S analysis over windows of increasing length."""
        signal_length = len(signal_array)
        log_n: list[float] = []
        log_rs: list[float] = []
        for length in HurstExponentEstimator._window_lengths(signal_length // 2):
            windows = signal_array[: (signal_length // length) * length].reshape(-1, length)
            deviations = np.cumsum(windows - windows.mean(axis=1, keepdims=True), axis=1)
            ranges = deviations.max(axis=1) - deviations.min(axis=1)
            std_devs = windows.std(axis=1, ddof=1)
            usable = std_devs > 0
            if np.any(usable):
                log_n.append(float(np.log(length)))
                log_rs.append(float(np.log(np.mean(ranges[usable] / std_devs[usable]))))
        return HurstExponentEstimator._slope(np.asarray(log_n), np.asarray(log_rs))

    @staticmethod
    def _hurst_dfa(signal_array: NDArray[np.float64]) -> float:
        """Hurst exponent via first-order detrended fluctuation analysis."""
        signal_length = len(signal_array)
        profile = np.cumsum(signal_array - np.mean(signal_array))
        log_n: list[float] = []
        log_f: list[float] = []
        for length in HurstExponentEstimator._window_lengths(signal_length // 4):
            windows = profile[: (signal_length // length) * length].reshape(-1, length)
            index = np.arange(length, dtype=float)
            # One least-squares line per window: lstsq on the shared design matrix.
            design = np.column_stack([index, np.ones(length)])
            coeffs, _, _, _ = np.linalg.lstsq(design, windows.T, rcond=None)
            residuals = windows.T - design @ coeffs
            fluctuation = float(np.sqrt(np.mean(residuals**2)))
            if fluctuation > 0:
                log_n.append(float(np.log(length)))
                log_f.append(float(np.log(fluctuation)))
        return HurstExponentEstimator._slope(np.asarray(log_n), np.asarray(log_f))

    @staticmethod
    def _hurst_wavelet(signal_array: NDArray[np.float64]) -> float:
        """Hurst exponent via the Abry-Veitch log-scale diagram on orthonormal Haar details."""
        approximation = signal_array.astype(float)
        octaves: list[float] = []
        log_energies: list[float] = []
        counts: list[float] = []
        octave = 0
        while approximation.size // 2 >= HurstExponentEstimator._min_octave_coefficients:
            octave += 1
            half = approximation.size // 2
            even = approximation[: 2 * half : 2]
            odd = approximation[1 : 2 * half : 2]
            detail = (even - odd) / np.sqrt(2.0)
            approximation = (even + odd) / np.sqrt(2.0)
            energy = float(np.mean(detail**2))
            if energy > 0:
                bias = -1.0 / (half * np.log(2.0))
                octaves.append(float(octave))
                log_energies.append(float(np.log2(energy)) - bias)
                counts.append(float(half))
        slope = HurstExponentEstimator._slope(
            np.asarray(octaves), np.asarray(log_energies), np.asarray(counts)
        )
        return (slope + 1.0) / 2.0

    @staticmethod
    def _compute_hurst(signal_array: NDArray[np.float64], method: str) -> float:
        """Validate one channel and dispatch to the selected method."""
        minimum = HurstExponentEstimator._min_samples[method]
        if signal_array.size < minimum:
            raise ValueError(
                f"HurstExponentEstimator: signal too short for method {method!r}: "
                f"{signal_array.size} samples, need at least {minimum}"
            )
        if float(np.ptp(signal_array)) == 0.0:
            raise ValueError("HurstExponentEstimator: a constant signal has no Hurst exponent")
        if method == "rs":
            return HurstExponentEstimator._hurst_rs(signal_array)
        if method == "dfa":
            return HurstExponentEstimator._hurst_dfa(signal_array)
        return HurstExponentEstimator._hurst_wavelet(signal_array)
