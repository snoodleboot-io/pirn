"""``TimeFrequencyDecomposer`` — Morlet / Multitaper time-frequency analysis.

Production version uses ``mne.time_frequency.tfr_morlet``. This stub
validates inputs and returns an empty mapping ``frequency -> power``.

Algorithm:
    1. Receive a SignalFrame, frequencies_hz sequence, and method string.
    2. Validate types and that all frequencies are positive and method is valid.
    3. Apply the time-frequency decomposition at the specified frequencies.
    4. Return a mapping of frequency to instantaneous power.

Math:
    $$W_f(t) = x(t) * \\psi_f(t), \\quad \\psi_f(t) = A e^{2\\pi i f t} e^{-t^2 / (2\\sigma_f^2)}$$

References:
    - MNE tfr_morlet: https://mne.tools/stable/generated/mne.time_frequency.tfr_morlet.html
    - Tallon-Baudry & Bertrand (1999) Oscillatory gamma activity in humans.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class TimeFrequencyDecomposer(Knot):
    """Decompose a signal into time-frequency representations."""

    def __init__(
        self,
        *,
        signal: Knot | SignalFrame,
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
        signal: SignalFrame,
        frequencies_hz: Sequence[float],
        method: str,
        **_: Any,
    ) -> Mapping[float, float]:
        """Decompose the signal at the configured frequencies using the configured method and return frequency-to-power mapping.

        Args:
            signal: The SignalFrame to decompose.
            frequencies_hz: Sequence of positive frequency values in Hz.
            method: Decomposition method; one of 'morlet', 'multitaper', 'stockwell'.

        Returns:
            A mapping from frequency (Hz) to estimated power.

        Raises:
            TypeError: If signal is not SignalFrame or frequencies_hz is not list/tuple.
            ValueError: If any frequency is non-positive or method is invalid.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("TimeFrequencyDecomposer: signal must be a SignalFrame")
        if not isinstance(frequencies_hz, (list, tuple)):
            raise TypeError("TimeFrequencyDecomposer: frequencies_hz must be list/tuple")
        for freq in frequencies_hz:
            if not isinstance(freq, (int, float)) or float(freq) <= 0:
                raise ValueError("TimeFrequencyDecomposer: every frequency must be positive")
        if method not in ("morlet", "multitaper", "stockwell"):
            raise ValueError(
                "TimeFrequencyDecomposer: method must be one of morlet/multitaper/stockwell"
            )
        return {float(f): 0.0 for f in frequencies_hz}
