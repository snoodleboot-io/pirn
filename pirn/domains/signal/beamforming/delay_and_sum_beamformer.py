"""``DelayAndSumBeamformer`` — classic delay-and-sum beamformer."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class DelayAndSumBeamformer(Knot):
    """Apply a delay-and-sum beamformer to a multi-element array signal."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: int,
        element_spacing_m: float,
        steering_angle_deg: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("DelayAndSumBeamformer: num_elements must be a positive integer")
        if not isinstance(element_spacing_m, (int, float)) or element_spacing_m <= 0:
            raise ValueError("DelayAndSumBeamformer: element_spacing_m must be a positive scalar")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("DelayAndSumBeamformer: steering_angle_deg must be a float")
        self._num_elements = num_elements
        self._element_spacing_m = float(element_spacing_m)
        self._steering_angle_deg = float(steering_angle_deg)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_elements(self) -> int:
        return self._num_elements

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the delay-and-sum beamformer and return the beamformed SignalFrame.

        Args:
            signal: The multi-element array input signal frame.

        Returns:
            SignalFrame representing the beamformed output channel.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:das",
            channel_count=1,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
