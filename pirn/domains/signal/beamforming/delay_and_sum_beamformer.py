"""``DelayAndSumBeamformer`` — classic delay-and-sum beamformer.

Algorithm:
    1. Receive the multi-element array signal frame and configuration parameters.
    2. Validate num_elements, element_spacing_m (positive), and steering_angle_deg (float).
    3. For each element i: compute the inter-element delay in samples:
       tau_i = i * element_spacing_m * sin(steering_angle_rad) / (c * T_s)
       where c = 343 m/s (speed of sound) and T_s = 1/sample_rate_hz.
    4. Fractionally delay each element signal by tau_i (via sinc interpolation or
       nearest-sample approximation).
    5. Sum all delayed element signals and normalise by num_elements.
    6. Return a single-channel beamformed SignalFrame.

Math:
    Delay for element $i$:

    $$\\tau_i = \\frac{i \\cdot d \\cdot \\sin\\theta}{c}$$

    where $d$ = element_spacing_m, $\\theta$ = steering_angle_deg in radians,
    $c \\approx 343$ m/s is the speed of sound.

    Beamformed output:

    $$y(n) = \\frac{1}{M} \\sum_{i=0}^{M-1} x_i\\!\\left(n - \\frac{\\tau_i}{T_s}\\right)$$

References:
    - Van Veen, B.D. & Buckley, K.M. (1988). "Beamforming: A versatile approach
      to spatial filtering." IEEE ASSP Magazine, 5(2), 4-24.
    - Johnson, D.H. & Dudgeon, D.E. (1993). "Array Signal Processing." Prentice Hall.
"""

from __future__ import annotations

from math import radians, sin
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _das_beamform(data: np.ndarray, delays_samples: np.ndarray) -> np.ndarray:
    n_ch = data.shape[0]
    out = np.zeros(data.shape[1])
    for i in range(n_ch):
        shift = round(delays_samples[i])
        out += np.roll(data[i], -shift)
    return out / n_ch


class DelayAndSumBeamformer(Knot):
    """Apply a delay-and-sum beamformer to a multi-element array signal."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: Knot | int,
        element_spacing_m: Knot | float,
        steering_angle_deg: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_elements=num_elements,
            element_spacing_m=element_spacing_m,
            steering_angle_deg=steering_angle_deg,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        num_elements: int,
        element_spacing_m: float,
        steering_angle_deg: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply the delay-and-sum beamformer and return the beamformed SignalFrame.

        Args:
            signal: The multi-element array input signal payload.
            num_elements: Number of array elements (positive integer).
            element_spacing_m: Distance between adjacent elements in metres (positive float).
            steering_angle_deg: Steering direction in degrees (float).

        Returns:
            Single-channel SignalPayload representing the beamformed output.

        Raises:
            ValueError: If num_elements or element_spacing_m are invalid.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("DelayAndSumBeamformer: num_elements must be a positive integer")
        if not isinstance(element_spacing_m, (int, float)) or element_spacing_m <= 0:
            raise ValueError("DelayAndSumBeamformer: element_spacing_m must be a positive scalar")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("DelayAndSumBeamformer: steering_angle_deg must be a float")

        import asyncio

        c = 343.0
        sample_rate_hz = signal.frame.sample_rate_hz
        data = signal.data
        delays_samples = np.array(
            [
                i * element_spacing_m * sin(radians(steering_angle_deg)) / (c / sample_rate_hz)
                for i in range(num_elements)
            ]
        )
        beamformed = await asyncio.to_thread(_das_beamform, data, delays_samples)
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:das",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.frame.samples_per_channel,
            ),
            data=beamformed[np.newaxis, :],
        )
