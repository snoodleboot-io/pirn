"""``MultiRateFusionPipeline`` — fuse two signals at different rates by resampling to a common rate."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MultiRateFusionPipeline(Knot):
    """Fuse two signals sampled at different rates by resampling both to a common output rate.

    Production needs ``scipy.signal.resample_poly``.
    """

    def __init__(
        self,
        *,
        signal_a: Knot,
        signal_b: Knot,
        output_rate_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(output_rate_hz, (int, float)) or output_rate_hz <= 0:
            raise ValueError(
                "MultiRateFusionPipeline: output_rate_hz must be positive"
            )
        self._output_rate_hz = float(output_rate_hz)
        super().__init__(signal_a=signal_a, signal_b=signal_b, _config=_config, **kwargs)

    @property
    def output_rate_hz(self) -> float:
        return self._output_rate_hz

    async def process(
        self,
        signal_a: SignalFrame,
        signal_b: SignalFrame,
        **_: Any,
    ) -> tuple[SignalFrame, SignalFrame]:
        """Resample both input signals to the common output rate and return the fused pair.

        Args:
            signal_a: First input signal at its native rate.
            signal_b: Second input signal at its native rate.

        Returns:
            Tuple of two SignalFrames, both resampled to ``output_rate_hz``.
        """
        def _resample(sf: SignalFrame, suffix: str) -> SignalFrame:
            ratio = self._output_rate_hz / max(sf.sample_rate_hz, 1.0)
            return SignalFrame(
                signal_id=f"{sf.signal_id}:{suffix}",
                channel_count=sf.channel_count,
                sample_rate_hz=self._output_rate_hz,
                samples_per_channel=int(sf.samples_per_channel * ratio),
            )

        return _resample(signal_a, "fused_a"), _resample(signal_b, "fused_b")
