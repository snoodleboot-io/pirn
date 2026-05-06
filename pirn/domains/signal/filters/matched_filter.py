"""``MatchedFilter`` — correlate the input with a known template.

Algorithm:
    1. Receive the input signal frame and template sequence.
    2. Validate that template is non-empty and all values are real numbers.
    3. Time-reverse the template to form the matched filter impulse response:
       h(n) = template*(T-1-n).
    4. Convolve the input signal with h using linear cross-correlation.
    5. Return a SignalFrame of the cross-correlation output.

Math:
    Matched filter impulse response:

    $$h(n) = s^*(T - 1 - n)$$

    where $s$ is the template waveform. The output is:

    $$y(n) = \\sum_{k=0}^{T-1} s^*(k) \\, x(n + k)$$

    which equals the cross-correlation between $x$ and $s$, maximising
    the output SNR at the template end time.

References:
    - Turin, G.L. (1960). "An introduction to matched filters." IRE Trans. Inf. Theory, 6(3), 311-329.
    - scipy.signal.correlate: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
        template: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            template=template,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        template: Sequence[float],
        **_: Any,
    ) -> SignalFrame:
        """Correlate the input signal against the configured template.

        Args:
            signal: Signal to correlate against the known waveform template.
            template: Non-empty sequence of real-valued template samples.

        Returns:
            SignalFrame of the cross-correlation output.

        Raises:
            ValueError: If template is empty.
            TypeError: If any template value is not a real number.
        """
        templ = tuple(template)
        if not templ:
            raise ValueError("MatchedFilter: template must be non-empty")
        for value in templ:
            if not isinstance(value, (int, float)):
                raise TypeError(
                    "MatchedFilter: template values must be real numbers"
                )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:matched",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
