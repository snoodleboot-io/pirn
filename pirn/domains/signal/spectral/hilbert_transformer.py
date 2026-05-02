"""``HilbertTransformer`` — analytic-signal construction via the Hilbert transform."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class HilbertTransformer(Knot):
    """Compute the analytic signal (90-degree phase shift via FFT).

    Production needs ``scipy.signal.hilbert``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(signal=signal, _config=_config, **kwargs)

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        return SignalFrame(
            signal_id=f"{signal.signal_id}:analytic",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
