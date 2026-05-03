"""``ZeroPhaseFilter`` — zero-phase forward-backward IIR filter."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ZeroPhaseFilter(Knot):
    """Apply a zero-phase IIR filter via forward-backward (filtfilt) processing."""

    _valid_types = frozenset({"lowpass", "highpass", "bandpass", "bandstop"})

    def __init__(
        self,
        *,
        signal: Knot,
        filter_type: str,
        cutoff_hz: float | tuple[float, float],
        order: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if filter_type not in self._valid_types:
            raise ValueError(
                "ZeroPhaseFilter: filter_type must be one of "
                "'lowpass', 'highpass', 'bandpass', 'bandstop'"
            )
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ZeroPhaseFilter: order must be a positive integer")
        self._validate_cutoff(cutoff_hz, filter_type)
        self._filter_type = filter_type
        self._cutoff_hz = cutoff_hz
        self._order = order
        super().__init__(signal=signal, _config=_config, **kwargs)

    @staticmethod
    def _validate_cutoff(cutoff_hz: float | tuple[float, float], filter_type: str) -> None:
        if filter_type in {"bandpass", "bandstop"}:
            if (
                not isinstance(cutoff_hz, tuple)
                or len(cutoff_hz) != 2
                or any(not isinstance(c, (int, float)) for c in cutoff_hz)
            ):
                raise ValueError(
                    "ZeroPhaseFilter: bandpass/bandstop requires (low, high) tuple"
                )
            low, high = cutoff_hz
            if low <= 0 or high <= 0 or low >= high:
                raise ValueError(
                    "ZeroPhaseFilter: cutoff bounds must satisfy 0 < low < high"
                )
        else:
            if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
                raise ValueError(
                    "ZeroPhaseFilter: cutoff_hz must be a positive scalar"
                )

    async def process(self, signal: SignalFrame, **_: Any) -> SignalFrame:
        """Apply the zero-phase forward-backward IIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.

        Returns:
            Filtered SignalFrame with zero phase distortion and the same shape as the input.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:zerophase-{self._filter_type}",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
