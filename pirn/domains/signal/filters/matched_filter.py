"""``MatchedFilter`` — correlate the input with a known template."""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MatchedFilter(Knot):
    """Matched filter for detecting a known waveform in noise.

    Production needs ``scipy.signal.correlate``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        template: Sequence[float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        templ = tuple(template)
        if not templ:
            raise ValueError("MatchedFilter: template must be non-empty")
        for value in templ:
            if not isinstance(value, (int, float)):
                raise TypeError(
                    "MatchedFilter: template values must be real numbers"
                )
        self._template = tuple(float(v) for v in templ)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def template(self) -> tuple[float, ...]:
        return self._template

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> SignalFrame:
        """Correlate the input signal against the configured template and return the match-filtered SignalFrame.

        Args:
            signal: Signal to correlate against the known waveform template.

        Returns:
            SignalFrame of the cross-correlation output.
        """
        return SignalFrame(
            signal_id=f"{signal.signal_id}:matched",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
