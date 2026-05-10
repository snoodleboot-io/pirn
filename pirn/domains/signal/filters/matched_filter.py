"""``MatchedFilter`` — correlate the input with a known template.

Algorithm:
    1. Receive the input signal payload and template sequence.
    2. Validate that template is non-empty and all values are real numbers.
    3. Apply scipy.signal.correlate per channel with mode='full'.
    4. Return a SignalPayload of the cross-correlation output.

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

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _correlate_multichannel(data: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Cross-correlate each channel of data with template, returning full-mode output."""
    if data.ndim == 1:
        return ss.correlate(data, template, mode="full")
    rows = [ss.correlate(data[i], template, mode="full") for i in range(data.shape[0])]
    return np.stack(rows, axis=0)


class MatchedFilter(Knot):
    """Matched filter for detecting a known waveform in noise."""

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
        signal: SignalPayload,
        template: Sequence[float],
        **_: Any,
    ) -> SignalPayload:
        """Correlate the input signal against the configured template.

        Args:
            signal: Signal payload to correlate against the known waveform template.
            template: Non-empty sequence of real-valued template samples.

        Returns:
            SignalPayload of the cross-correlation output.

        Raises:
            ValueError: If template is empty.
            TypeError: If any template value is not a real number.
        """
        templ = tuple(template)
        if not templ:
            raise ValueError("MatchedFilter: template must be non-empty")
        for value in templ:
            if not isinstance(value, (int, float)):
                raise TypeError("MatchedFilter: template values must be real numbers")

        tmpl_arr = np.array(templ)
        out_samples = signal.data.shape[-1] + len(templ) - 1
        filtered = await asyncio.to_thread(_correlate_multichannel, signal.data, tmpl_arr)
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:matched",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=out_samples,
            ),
            data=np.asarray(filtered),
        )
