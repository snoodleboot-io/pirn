"""``PolyphaseDecimator`` — efficient downsampling via polyphase FIR.

Algorithm:
    1. Receive the input signal payload, decimation_factor, and filter_taps.
    2. Validate decimation_factor (integer > 1) and filter_taps (positive integer).
    3. Apply scipy.signal.decimate(data, q=decimation_factor, ftype='fir',
       zero_phase=True, axis=-1).
    4. Return a SignalPayload at the reduced sample rate.

Math:
    Polyphase decomposition of prototype filter $H(z)$:

    $$H(z) = \\sum_{k=0}^{M-1} z^{-k} E_k(z^M)$$

    Decimated output sample rate:

    $$f_{s,\\text{out}} = \\frac{f_s}{M}, \\quad N_{\\text{out}} = \\left\\lfloor \\frac{N_{\\text{in}}}{M} \\right\\rfloor$$

References:
    - Crochiere, R.E. & Rabiner, L.R. (1983). "Multirate Digital Signal Processing."
      Prentice-Hall.
    - scipy.signal.decimate: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.decimate.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from scipy import signal as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


class PolyphaseDecimator(Knot):
    """Polyphase FIR decimator (anti-alias filter + downsample)."""

    def __init__(
        self,
        *,
        signal: Knot,
        decimation_factor: Knot | int,
        filter_taps: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            decimation_factor=decimation_factor,
            filter_taps=filter_taps,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        decimation_factor: int,
        filter_taps: int,
        **_: Any,
    ) -> SignalPayload:
        """Anti-alias filter and downsample the input signal by the configured factor.

        Args:
            signal: Signal payload to anti-alias filter and downsample.
            decimation_factor: Downsampling factor (integer > 1).
            filter_taps: Number of anti-aliasing FIR taps (positive integer).

        Returns:
            SignalPayload at the reduced sample rate with a proportionally smaller sample count.

        Raises:
            ValueError: If decimation_factor or filter_taps are invalid.
        """
        if not isinstance(decimation_factor, int) or decimation_factor <= 1:
            raise ValueError("PolyphaseDecimator: decimation_factor must be an integer > 1")
        if not isinstance(filter_taps, int) or filter_taps <= 0:
            raise ValueError("PolyphaseDecimator: filter_taps must be a positive integer")

        decimated = await asyncio.to_thread(
            ss.decimate, signal.data, decimation_factor, ftype="fir", zero_phase=True, axis=-1
        )
        new_rate = signal.frame.sample_rate_hz / decimation_factor
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:polyphase-dec",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=new_rate,
                samples_per_channel=decimated.shape[-1],
            ),
            data=np.asarray(decimated),
        )
