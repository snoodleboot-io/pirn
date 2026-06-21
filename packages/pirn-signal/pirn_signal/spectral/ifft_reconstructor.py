"""``IFFTReconstructor`` — reconstruct a time-domain signal from a spectrum via IFFT.

Algorithm:
    1. Receive the input spectrum payload.
    2. Apply ``np.fft.irfft`` to recover the real-valued time-domain signal.
    3. Return a SignalPayload with samples_per_channel = 2 * (freq_bins - 1).

Math:
    Inverse DFT:

    $$x[n] = \\frac{1}{N} \\sum_{k=0}^{N-1} X[k] e^{j 2\\pi k n / N}$$

References:
    - Cooley, J.W. & Tukey, J.W. (1965). "An algorithm for the machine computation of complex
      Fourier series." Math. Comp., 19(90), 297-301.
    - scipy.fft.irfft: https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.irfft.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_payload import SpectrumPayload


class IFFTReconstructor(Knot):
    """Apply the inverse FFT to a SpectrumPayload and reconstruct the time-domain SignalPayload."""

    def __init__(
        self,
        *,
        spectrum: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(spectrum=spectrum, _config=_config, **kwargs)

    async def process(self, spectrum: SpectrumPayload, **_: Any) -> SignalPayload:
        """Reconstruct the time-domain signal from the spectrum via IFFT.

        Args:
            spectrum: The frequency-domain SpectrumPayload to invert.

        Returns:
            SignalPayload with samples derived from the spectrum data.
        """
        samples = await asyncio.to_thread(np.fft.irfft, spectrum.data, axis=-1)
        n_samples = samples.shape[-1]

        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{spectrum.frame.signal_id}:ifft",
                channel_count=1,
                sample_rate_hz=0.0,
                samples_per_channel=n_samples,
            ),
            data=samples,
        )
