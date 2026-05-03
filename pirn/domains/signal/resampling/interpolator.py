"""``Interpolator`` — generic interpolation knot."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class Interpolator(Knot):
    """Interpolate a signal to a new (higher) sample rate.

    Production needs ``scipy.interpolate`` or ``scipy.signal``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        target_sample_rate_hz: float,
        kind: str = "cubic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if (
            not isinstance(target_sample_rate_hz, (int, float))
            or target_sample_rate_hz <= 0
        ):
            raise ValueError(
                "Interpolator: target_sample_rate_hz must be positive"
            )
        if kind not in {"linear", "cubic", "quadratic", "spline"}:
            raise ValueError(
                "Interpolator: kind must be 'linear', 'cubic', 'quadratic', or 'spline'"
            )
        self._target_sample_rate_hz = float(target_sample_rate_hz)
        self._kind = kind
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def target_sample_rate_hz(self) -> float:
        return self._target_sample_rate_hz

    @property
    def kind(self) -> str:
        return self._kind

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Interpolate the signal to the configured target sample rate and return the upsampled SignalFrame.

        Args:
            signal: Signal to interpolate to a higher sample rate.

        Returns:
            SignalFrame at the configured target sample rate with an adjusted sample count.
        """
        if signal.sample_rate_hz > 0:
            ratio = self._target_sample_rate_hz / signal.sample_rate_hz
            new_samples = int(signal.samples_per_channel * ratio)
        else:
            new_samples = signal.samples_per_channel
        return SignalFrame(
            signal_id=f"{signal.signal_id}:interp",
            channel_count=signal.channel_count,
            sample_rate_hz=self._target_sample_rate_hz,
            samples_per_channel=new_samples,
        )
