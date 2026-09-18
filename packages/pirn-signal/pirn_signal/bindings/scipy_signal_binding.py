"""``ScipySignalBinding`` — typed boundary over ``scipy.signal``.

``scipy`` ships no type stubs; strict pyright reports every attribute of the
module as partially unknown. This binding performs the lazy optional-extra
import once and exposes the filter-design, filtering and spectral-estimation calls the knots use with
real ``NDArray`` annotations.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pirn.core.optional_dependency import OptionalDependency


class ScipySignalBinding:
    """Annotated facade over the ``scipy.signal`` functions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> ScipySignalBinding:
        """Import ``scipy.signal`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``scipy.signal`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(
            OptionalDependency.require("scipy.signal", extra="signal", package="pirn-signal")
        )

    # --- IIR design (second-order sections) ----------------------------------

    def butter_sos(
        self, order: int, cutoff_hz: float | Sequence[float], btype: str, fs: float
    ) -> NDArray[np.float64]:
        """Design a Butterworth filter as second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.butter(order, cutoff_hz, btype=btype, fs=fs, output="sos"),
            dtype=np.float64,
        )
        return sos

    def cheby1_sos(
        self, order: int, ripple_db: float, cutoff_hz: float, btype: str, fs: float
    ) -> NDArray[np.float64]:
        """Design a Chebyshev type-I filter as second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.cheby1(order, ripple_db, cutoff_hz, btype=btype, fs=fs, output="sos"),
            dtype=np.float64,
        )
        return sos

    def cheby2_sos(
        self, order: int, attenuation_db: float, cutoff_hz: float, btype: str, fs: float
    ) -> NDArray[np.float64]:
        """Design a Chebyshev type-II filter as second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.cheby2(order, attenuation_db, cutoff_hz, btype=btype, fs=fs, output="sos"),
            dtype=np.float64,
        )
        return sos

    def ellip_sos(
        self,
        order: int,
        ripple_db: float,
        attenuation_db: float,
        cutoff_hz: float,
        btype: str,
        fs: float,
    ) -> NDArray[np.float64]:
        """Design an elliptic (Cauer) filter as second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.ellip(
                order, ripple_db, attenuation_db, cutoff_hz, btype=btype, fs=fs, output="sos"
            ),
            dtype=np.float64,
        )
        return sos

    def bessel_sos(
        self, order: int, cutoff_hz: float, btype: str, fs: float
    ) -> NDArray[np.float64]:
        """Design a Bessel/Thomson filter as second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.bessel(order, cutoff_hz, btype, fs=fs, output="sos"),
            dtype=np.float64,
        )
        return sos

    def iirnotch(
        self, notch_hz: float, quality_factor: float, fs: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Design a second-order IIR notch filter; returns ``(b, a)``."""
        coefficients: tuple[NDArray[np.float64], NDArray[np.float64]] = self._module.iirnotch(
            notch_hz, quality_factor, fs
        )
        return coefficients

    def tf2sos(self, numerator: ArrayLike, denominator: ArrayLike) -> NDArray[np.float64]:
        """Convert transfer-function coefficients ``(b, a)`` to second-order sections."""
        sos: NDArray[np.float64] = np.asarray(
            self._module.tf2sos(numerator, denominator), dtype=np.float64
        )
        return sos

    # --- FIR design ----------------------------------------------------------

    def firwin(
        self, num_taps: int, cutoff_hz: float | Sequence[float], window: str, fs: float
    ) -> NDArray[np.float64]:
        """Design a windowed-sinc FIR filter; returns the tap weights."""
        taps: NDArray[np.float64] = np.asarray(
            self._module.firwin(num_taps, cutoff_hz, window=window, fs=fs), dtype=np.float64
        )
        return taps

    def remez(
        self, num_taps: int, bands: Sequence[float], desired: Sequence[float], fs: float
    ) -> NDArray[np.float64]:
        """Design an equiripple (Parks-McClellan) FIR filter; returns the tap weights."""
        taps: NDArray[np.float64] = np.asarray(
            self._module.remez(num_taps, list(bands), list(desired), fs=fs), dtype=np.float64
        )
        return taps

    # --- filtering -----------------------------------------------------------

    def sosfilt(self, sos: ArrayLike, data: ArrayLike, axis: int = -1) -> NDArray[np.floating[Any]]:
        """Filter ``data`` causally with second-order sections along ``axis``."""
        filtered: NDArray[np.floating[Any]] = self._module.sosfilt(sos, data, axis=axis)
        return filtered

    def sosfiltfilt(
        self, sos: ArrayLike, data: ArrayLike, axis: int = -1
    ) -> NDArray[np.floating[Any]]:
        """Filter ``data`` forward-backward (zero phase) with second-order sections."""
        filtered: NDArray[np.floating[Any]] = self._module.sosfiltfilt(sos, data, axis=axis)
        return filtered

    def lfilter(
        self, numerator: ArrayLike, denominator: ArrayLike, data: ArrayLike, axis: int = -1
    ) -> NDArray[np.floating[Any]]:
        """Filter ``data`` with the transfer function ``(b, a)`` along ``axis``."""
        filtered: NDArray[np.floating[Any]] = self._module.lfilter(
            numerator, denominator, data, axis=axis
        )
        return filtered

    def savgol_filter(
        self, data: ArrayLike, window_length: int, polynomial_order: int, axis: int = -1
    ) -> NDArray[np.floating[Any]]:
        """Apply a Savitzky-Golay smoothing filter along ``axis``."""
        filtered: NDArray[np.floating[Any]] = self._module.savgol_filter(
            data, window_length, polynomial_order, axis=axis
        )
        return filtered

    def wiener(
        self, data: ArrayLike, window_size: int, noise_power: float | None
    ) -> NDArray[np.floating[Any]]:
        """Apply a Wiener filter with a local statistics window of ``window_size``."""
        filtered: NDArray[np.floating[Any]] = self._module.wiener(
            data, mysize=window_size, noise=noise_power
        )
        return filtered

    def decimate(
        self,
        data: ArrayLike,
        factor: int,
        ftype: str = "iir",
        zero_phase: bool = True,
        axis: int = -1,
    ) -> NDArray[np.floating[Any]]:
        """Anti-alias filter and downsample ``data`` by ``factor``."""
        decimated: NDArray[np.floating[Any]] = self._module.decimate(
            data, factor, ftype=ftype, zero_phase=zero_phase, axis=axis
        )
        return decimated

    def resample_poly(
        self,
        data: ArrayLike,
        up: int,
        down: int,
        axis: int = -1,
        window: NDArray[np.float64] | None = None,
    ) -> NDArray[np.floating[Any]]:
        """Resample ``data`` by the rational factor ``up / down`` with a polyphase filter.

        Args:
            data: Samples to resample.
            up: Upsampling factor.
            down: Downsampling factor.
            axis: Axis along which to resample.
            window: FIR anti-alias coefficients to use, already scaled for the
                upsampling gain. ``None`` leaves scipy's default Kaiser design,
                whose length scipy derives from ``up``/``down``.

        Returns:
            The resampled array.
        """
        if window is None:
            default: NDArray[np.floating[Any]] = self._module.resample_poly(
                data, up, down, axis=axis
            )
            return default
        resampled: NDArray[np.floating[Any]] = self._module.resample_poly(
            data, up, down, axis=axis, window=window
        )
        return resampled

    def correlate(
        self, first: ArrayLike, second: ArrayLike, mode: str = "full"
    ) -> NDArray[np.floating[Any]]:
        """Cross-correlate two real arrays."""
        correlation: NDArray[np.floating[Any]] = self._module.correlate(first, second, mode=mode)
        return correlation

    # --- analytic signal and spectral estimation -----------------------------

    def hilbert(self, data: ArrayLike, axis: int = -1) -> NDArray[np.complexfloating[Any, Any]]:
        """Compute the analytic signal of ``data`` along ``axis``."""
        analytic: NDArray[np.complexfloating[Any, Any]] = self._module.hilbert(data, axis=axis)
        return analytic

    def welch(
        self,
        data: ArrayLike,
        fs: float,
        window: str,
        nperseg: int,
        noverlap: int,
        axis: int = -1,
    ) -> tuple[NDArray[np.float64], NDArray[np.floating[Any]]]:
        """Estimate the PSD with Welch's method; returns ``(frequencies, pxx)``."""
        result: tuple[NDArray[np.float64], NDArray[np.floating[Any]]] = self._module.welch(
            data, fs=fs, window=window, nperseg=nperseg, noverlap=noverlap, axis=axis
        )
        return result

    def periodogram(
        self, data: ArrayLike, fs: float, window: str, axis: int = -1
    ) -> tuple[NDArray[np.float64], NDArray[np.floating[Any]]]:
        """Estimate the PSD with a windowed periodogram; returns ``(frequencies, pxx)``."""
        result: tuple[NDArray[np.float64], NDArray[np.floating[Any]]] = self._module.periodogram(
            data, fs=fs, window=window, axis=axis
        )
        return result

    def csd(
        self, first: ArrayLike, second: ArrayLike, fs: float, nperseg: int, axis: int = -1
    ) -> tuple[NDArray[np.float64], NDArray[np.complexfloating[Any, Any]]]:
        """Estimate the cross power spectral density; returns ``(frequencies, pxy)``."""
        result: tuple[NDArray[np.float64], NDArray[np.complexfloating[Any, Any]]] = (
            self._module.csd(first, second, fs=fs, nperseg=nperseg, axis=axis)
        )
        return result

    def stft(
        self,
        data: ArrayLike,
        fs: float,
        window: str,
        nperseg: int,
        noverlap: int,
        axis: int = -1,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.complexfloating[Any, Any]]]:
        """Short-time Fourier transform; returns ``(frequencies, times, zxx)``."""
        result: tuple[
            NDArray[np.float64], NDArray[np.float64], NDArray[np.complexfloating[Any, Any]]
        ] = self._module.stft(
            data, fs=fs, window=window, nperseg=nperseg, noverlap=noverlap, axis=axis
        )
        return result

    def istft(
        self,
        zxx: ArrayLike,
        fs: float,
        window: str,
        nperseg: int,
        noverlap: int,
        freq_axis: int = -2,
        time_axis: int = -1,
    ) -> tuple[NDArray[np.float64], NDArray[np.floating[Any]]]:
        """Inverse short-time Fourier transform; returns ``(times, samples)``."""
        result: tuple[NDArray[np.float64], NDArray[np.floating[Any]]] = self._module.istft(
            zxx,
            fs=fs,
            window=window,
            nperseg=nperseg,
            noverlap=noverlap,
            freq_axis=freq_axis,
            time_axis=time_axis,
        )
        return result

    def spectrogram(
        self,
        data: ArrayLike,
        fs: float,
        window: str,
        nperseg: int,
        noverlap: int,
        scaling: str,
        axis: int = -1,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.floating[Any]]]:
        """Compute a spectrogram; returns ``(frequencies, times, sxx)``."""
        result: tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.floating[Any]]] = (
            self._module.spectrogram(
                data,
                fs=fs,
                window=window,
                nperseg=nperseg,
                noverlap=noverlap,
                scaling=scaling,
                axis=axis,
            )
        )
        return result

    # --- waveforms and windows -----------------------------------------------

    def chirp(self, t: ArrayLike, f0: float, t1: float, f1: float) -> NDArray[np.float64]:
        """Evaluate a linear frequency-swept cosine at times ``t``."""
        waveform: NDArray[np.float64] = np.asarray(
            self._module.chirp(t, f0=f0, t1=t1, f1=f1), dtype=np.float64
        )
        return waveform

    def hann(self, length: int) -> NDArray[np.float64]:
        """Return a symmetric Hann window of ``length`` samples."""
        window: NDArray[np.float64] = np.asarray(
            self._module.windows.hann(length), dtype=np.float64
        )
        return window

    def dpss(self, length: int, time_bandwidth: float, taper_count: int) -> NDArray[np.float64]:
        """Return ``taper_count`` discrete prolate spheroidal tapers, shaped ``(K, length)``.

        The tapers are real-valued, so the float64 coercion is exact.
        """
        tapers: NDArray[np.float64] = np.asarray(
            self._module.windows.dpss(length, time_bandwidth, Kmax=taper_count),
            dtype=np.float64,
        )
        return tapers
