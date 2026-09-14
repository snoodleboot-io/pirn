"""``ChirpletDecomposer`` — chirplet-transform decomposition.

Algorithm:
    1. Receive the input signal payload and chirplet_count.
    2. Validate chirplet_count (positive integer).
    3. For each of chirplet_count chirp atoms at linearly spaced frequencies:
       modulate signal with chirp, apply Hann window, FFT.
    4. Return a SpectrumPayload with frequency_bins = chirplet_count.

Math:
    Chirplet atom:

    $$g_{f_0}(t) = w(t) \\cdot e^{j 2\\pi f_0 t}$$

References:
    - Mann, S. & Haykin, S. (1995). "The chirplet transform: Physical considerations."
      IEEE Trans. Signal Process., 43(11), 2745-2761.
    - scipy.signal.chirp: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.chirp.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.scipy_signal_binding import ScipySignalBinding
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


class ChirpletDecomposer(Knot):
    """Chirplet-transform decomposition for non-stationary signals."""

    def __init__(
        self,
        *,
        signal: Knot,
        chirplet_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            chirplet_count=chirplet_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        chirplet_count: int,
        **_: Any,
    ) -> SpectrumPayload:
        """Decompose the signal into chirplet atoms and return a SpectrumPayload.

        Args:
            signal: Non-stationary signal payload to decompose using the chirplet transform.
            chirplet_count: Number of chirplet atoms / frequency scales (positive integer).

        Returns:
            SpectrumPayload with chirplet coefficients and frequency_bins = chirplet_count.

        Raises:
            ValueError: If chirplet_count is not a positive integer.
        """
        if not isinstance(chirplet_count, int) or chirplet_count <= 0:
            raise ValueError("ChirpletDecomposer: chirplet_count must be a positive integer")

        stacked = await asyncio.to_thread(
            ChirpletDecomposer._compute_chirplets,
            signal.data,
            signal.frame.sample_rate_hz,
            chirplet_count,
        )

        return SpectrumPayload(
            metadata=SpectrumFrame(
                signal_id=signal.frame.signal_id,
                frequency_bins=chirplet_count,
                frequency_resolution_hz=0.0,
            ),
            data=stacked,
        )

    @staticmethod
    def _compute_chirplets(
        data: NDArray[np.floating[Any]],
        sample_rate: float,
        chirplet_count: int,
    ) -> NDArray[np.complexfloating[Any, Any]]:
        ss = ScipySignalBinding.load()
        sample_count = data.shape[-1]
        time_axis: NDArray[np.float64] = (
            np.arange(sample_count, dtype=np.float64) / sample_rate
            if sample_rate > 0
            else np.arange(sample_count, dtype=float)
        )
        nyquist = sample_rate / 2.0 if sample_rate > 0 else 0.5
        freqs = np.linspace(0.0, nyquist, chirplet_count, endpoint=False)
        window = ss.hann(sample_count)
        results: list[NDArray[np.complexfloating[Any, Any]]] = []
        for f0 in freqs:
            f1 = min(float(f0) + nyquist / chirplet_count, nyquist)
            t_end = float(time_axis[-1]) if len(time_axis) > 1 else 1.0
            chirp_atom: NDArray[np.float64] = (
                ss.chirp(time_axis, f0=float(f0), t1=t_end, f1=f1) * window
            )
            modulated = data * chirp_atom
            spectrum = np.fft.rfft(modulated, axis=-1)
            results.append(spectrum[..., 0])
        return np.stack(results, axis=-1)
