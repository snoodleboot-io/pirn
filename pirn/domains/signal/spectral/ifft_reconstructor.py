"""``IFFTReconstructor`` — reconstruct a time-domain signal from a spectrum via IFFT.

Algorithm:
    1. Receive the input spectrum frame.
    2. Interpret the one-sided spectrum (frequency_bins = n_fft / 2 + 1).
    3. Reconstruct the two-sided complex spectrum via conjugate symmetry.
    4. Apply the inverse FFT to recover the real-valued time-domain signal.
    5. Return a SignalFrame with samples_per_channel = (frequency_bins - 1) * 2.

Math:
    Inverse DFT:

    $$x[n] = \\frac{1}{N} \\sum_{k=0}^{N-1} X[k] e^{j 2\\pi k n / N}$$

    One-sided to two-sided conversion (Hermitian symmetry):

    $$X[N-k] = X^*[k], \\quad k = 1, 2, \\ldots, N/2 - 1$$

References:
    - Cooley, J.W. & Tukey, J.W. (1965). "An algorithm for the machine computation of complex
      Fourier series." Math. Comp., 19(90), 297-301.
    - scipy.fft.irfft: https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.irfft.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class IFFTReconstructor(Knot):
    """Apply the inverse FFT to a SpectrumFrame and reconstruct the time-domain SignalFrame."""

    def __init__(
        self,
        *,
        spectrum: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(spectrum=spectrum, _config=_config, **kwargs)

    async def process(self, spectrum: SpectrumFrame, **_: Any) -> SignalFrame:
        """Reconstruct the time-domain signal from the spectrum via IFFT.

        Args:
            spectrum: The frequency-domain SpectrumFrame to invert.

        Returns:
            SignalFrame with num_samples derived from the spectrum bin count.
        """
        n_samples = (spectrum.frequency_bins - 1) * 2
        return SignalFrame(
            signal_id=f"{spectrum.signal_id}:ifft",
            channel_count=1,
            sample_rate_hz=0.0,
            samples_per_channel=n_samples,
        )
