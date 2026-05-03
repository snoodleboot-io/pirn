"""``BeamformerMVDR`` — minimum variance distortionless response beamformer."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class BeamformerMVDR(Knot):
    """Apply an MVDR (Capon) beamformer with optional diagonal loading for robustness."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: int,
        steering_angle_deg: float,
        diagonal_loading: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMVDR: num_elements must be a positive integer")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("BeamformerMVDR: steering_angle_deg must be a float")
        if not isinstance(diagonal_loading, (int, float)) or diagonal_loading < 0.0:
            raise ValueError("BeamformerMVDR: diagonal_loading must be >= 0.0")
        self._num_elements = num_elements
        self._steering_angle_deg = float(steering_angle_deg)
        self._diagonal_loading = float(diagonal_loading)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_elements(self) -> int:
        return self._num_elements

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the MVDR beamformer and return the beamformed SignalFrame.

        Args:
            signal: The multi-element array input signal frame.

        Returns:
            SignalFrame representing the MVDR beamformed output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:mvdr",
            channel_count=1,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
