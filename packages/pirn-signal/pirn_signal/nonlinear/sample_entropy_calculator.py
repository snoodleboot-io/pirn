"""``SampleEntropyCalculator`` — sample entropy of a time series.

Algorithm:
    1. Receive the input signal frame, m (template length), and r (tolerance).
    2. Validate m (positive integer) and r (positive float).
    3. For each pair of subsequences of length m, count matches where the
       Chebyshev distance is less than r (count B).
    4. Repeat for subsequences of length m+1 (count A).
    5. Compute SampEn = -ln(A / B).
    6. Repeat independently for each channel and return a FeaturePayload with
       one sample entropy value per channel.

Math:
    Sample entropy:

    $$\\text{SampEn}(m, r, N) = -\\ln \\frac{A^m(r)}{B^m(r)}$$

    where $A^m(r)$ = number of template matches of length $m+1$,
    $B^m(r)$ = number of template matches of length $m$,
    and $r$ is the tolerance expressed as a fraction of the signal's
    standard deviation.

References:
    - Richman, J.S. & Moorman, J.R. (2000). "Physiological time-series analysis using
      approximate entropy and sample entropy." Am. J. Physiol., 278(6), H2039-H2049.
    - antropy library: https://github.com/raphaelvallat/antropy
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.nonlinear._sample_entropy import SampleEntropy
from pirn_signal.types.feature_frame import FeatureFrame
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload


class SampleEntropyCalculator(Knot):
    """Compute sample entropy of a time series signal."""

    def __init__(
        self,
        *,
        signal: Knot,
        template_length: Knot | int,
        tolerance: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            template_length=template_length,
            tolerance=tolerance,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        template_length: int,
        tolerance: float,
        **_: Any,
    ) -> FeaturePayload:
        """Compute sample entropy of the signal using template matching.

        Args:
            signal: Signal payload to analyse.
            template_length: Template length for pattern matching (positive integer).
            tolerance: Tolerance for template matching (positive float).

        Returns:
            FeaturePayload with one ``sample_entropy`` value per channel.

        Raises:
            ValueError: If template_length or tolerance are invalid.
        """
        if not isinstance(template_length, int) or template_length <= 0:
            raise ValueError("SampleEntropyCalculator: template_length must be a positive integer")
        if not isinstance(tolerance, (int, float)) or tolerance <= 0.0:
            raise ValueError("SampleEntropyCalculator: tolerance must be a positive float")
        channels = np.atleast_2d(signal.data).astype(float)
        values = await asyncio.gather(
            *(
                asyncio.to_thread(SampleEntropy.compute, channel, template_length, float(tolerance))
                for channel in channels
            )
        )
        return FeaturePayload(
            metadata=FeatureFrame(
                signal_id=f"{signal.metadata.signal_id}:sample-entropy",
                channel_count=channels.shape[0],
                feature_names=("sample_entropy",),
            ),
            data=np.asarray(values).reshape(channels.shape[0], 1),
        )
