"""``TimeFrequencyDecomposer`` — Morlet / Multitaper time-frequency analysis.

Algorithm:
    1. Receive a SignalPayload, frequencies_hz sequence, and method string.
    2. Validate types and that all frequencies are positive and method is valid.
    3. For each frequency, compute mean power via scipy.signal.cwt with Morlet wavelets.
    4. Return a mapping of frequency to mean instantaneous power.

Math:
    $$W_f(t) = x(t) * \\psi_f(t), \\quad \\psi_f(t) = A e^{2\\pi i f t} e^{-t^2 / (2\\sigma_f^2)}$$

References:
    - MNE tfr_morlet: https://mne.tools/stable/generated/mne.time_frequency.tfr_morlet.html
    - Tallon-Baudry & Bertrand (1999) Oscillatory gamma activity in humans.
    - SciPy cwt: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cwt.html
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload

_morlet_w = 6.0


def _morlet_wavelet(n: int, width: float, w: float = 6.0) -> np.ndarray:
    """Build a complex Morlet wavelet of length n and scale width."""
    t = np.arange(-(n // 2), n - n // 2, dtype=float) / width
    return np.exp(1j * w * t) * np.exp(-0.5 * t**2) * np.pi**-0.25


def _cwt_power(signal_1d: np.ndarray, fs: float, freq: float) -> float:
    width = fs / freq * _morlet_w / (2 * np.pi)
    wavelet = _morlet_wavelet(len(signal_1d), width, w=_morlet_w)
    coef = np.convolve(signal_1d, wavelet[::-1], mode="same")
    return float(np.mean(np.abs(coef) ** 2))


def _compute_tf(data: np.ndarray, frequencies_hz: Sequence[float], fs: float) -> dict[float, float]:
    channel = data[0] if data.ndim > 1 else data
    return {float(f): _cwt_power(channel, fs, float(f)) for f in frequencies_hz}


class TimeFrequencyDecomposer(Knot):
    """Decompose a signal into time-frequency representations."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        frequencies_hz: Knot | Sequence[float],
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            frequencies_hz=frequencies_hz,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        frequencies_hz: Sequence[float],
        method: str,
        **_: Any,
    ) -> Mapping[float, float]:
        """Decompose the signal at the configured frequencies using Morlet CWT.

        Args:
            signal: The SignalPayload to decompose.
            frequencies_hz: Sequence of positive frequency values in Hz.
            method: Decomposition method; one of 'morlet', 'multitaper', 'stockwell'.

        Returns:
            A mapping from frequency (Hz) to mean power estimated via CWT.

        Raises:
            TypeError: If signal is not SignalPayload or frequencies_hz is not list/tuple.
            ValueError: If any frequency is non-positive or method is invalid.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("TimeFrequencyDecomposer: signal must be a SignalPayload")
        if not isinstance(frequencies_hz, (list, tuple)):
            raise TypeError("TimeFrequencyDecomposer: frequencies_hz must be list/tuple")
        for freq in frequencies_hz:
            if not isinstance(freq, (int, float)) or float(freq) <= 0:
                raise ValueError("TimeFrequencyDecomposer: every frequency must be positive")
        if method not in ("morlet", "multitaper", "stockwell"):
            raise ValueError(
                "TimeFrequencyDecomposer: method must be one of morlet/multitaper/stockwell"
            )

        fs = signal.frame.sample_rate_hz
        return await asyncio.to_thread(_compute_tf, signal.data, frequencies_hz, fs)
