"""``IFFTReconstructor`` — reconstruct a time-domain signal from a spectrum via IFFT."""

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
