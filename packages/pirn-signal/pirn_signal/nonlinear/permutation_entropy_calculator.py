"""``PermutationEntropyCalculator`` — ordinal pattern complexity measure.

Algorithm:
    1. Receive the input signal frame, order, and delay.
    2. Validate order (integer in [2, 8]) and delay (positive integer).
    3. Extract all overlapping subsequences of length ``order`` spaced by ``delay``.
    4. Map each subsequence to its ordinal rank pattern (one of ``order!`` possible patterns).
    5. Compute the empirical frequency distribution of ordinal patterns.
    6. Apply the Shannon entropy formula to the distribution; normalise by log(order!).
    7. Repeat independently for each channel and return a FeaturePayload with
       one permutation entropy value per channel.

Math:
    Permutation entropy:

    $$H(m) = -\\sum_{\\pi} p(\\pi) \\ln p(\\pi)$$

    Normalised permutation entropy:

    $$\\tilde{H}(m) = \\frac{H(m)}{\\ln(m!)}$$

    where $m$ = order and $p(\\pi)$ is the empirical probability of ordinal pattern $\\pi$.

References:
    - Bandt, C. & Pompe, B. (2002). "Permutation entropy: a natural complexity measure for
      time series." Phys. Rev. Lett., 88(17), 174102.
    - antropy library: https://github.com/raphaelvallat/antropy
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.nonlinear._ordinal_pattern_entropy import OrdinalPatternEntropy
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class PermutationEntropyCalculator(Knot):
    """Compute permutation entropy and normalised permutation entropy."""

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        delay: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            delay=delay,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        order: int,
        delay: int,
        **_: Any,
    ) -> FeaturePayload:
        """Compute permutation entropy from ordinal patterns in the signal.

        Args:
            signal: Signal payload to analyse.
            order: Ordinal pattern length (integer in [2, 8]).
            delay: Sample lag between pattern elements (positive integer).

        Returns:
            FeaturePayload with one ``permutation_entropy`` value per channel.

        Raises:
            ValueError: If order or delay are invalid.
        """
        if not isinstance(order, int) or order < 2 or order > 8:
            raise ValueError("PermutationEntropyCalculator: order must be an integer in [2, 8]")
        if not isinstance(delay, int) or delay <= 0:
            raise ValueError("PermutationEntropyCalculator: delay must be a positive integer")
        channels = np.atleast_2d(signal.data).astype(float)
        values = await asyncio.gather(
            *(
                PermutationEntropyCalculator._entropy_of_channel(channel, order, delay)
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.frame.signal_id}:permutation-entropy",
                channel_count=channels.shape[0],
                feature_names=("permutation_entropy",),
            ),
            data=np.asarray(values).reshape(channels.shape[0], 1),
        )

    @staticmethod
    async def _entropy_of_channel(channel: np.ndarray, order: int, delay: int) -> float:
        """Compute the (non-normalised) permutation entropy of a single channel."""
        result: tuple[float, float] = await asyncio.to_thread(
            OrdinalPatternEntropy.compute, channel, order, delay
        )
        return result[0]
