"""``BeamformerMVDR`` — minimum variance distortionless response beamformer.

Algorithm:
    1. Receive the multi-element array signal frame and configuration parameters.
    2. Validate num_elements, steering_angle_deg (float), and diagonal_loading (>= 0).
    3. Compute the sample covariance matrix R = (1/N) X X^H.
    4. Apply diagonal loading: R_l = R + diagonal_loading * I for robustness.
    5. Construct the steering vector a(theta) for the given steering_angle_deg.
    6. Compute MVDR weights: w = R_l^{-1} a / (a^H R_l^{-1} a).
    7. Apply weights to the array signal: y = w^H X.
    8. Return a single-channel beamformed SignalFrame.

Math:
    MVDR weight vector:

    $$\\mathbf{w}_{\\text{MVDR}} = \\frac{\\mathbf{R}_l^{-1} \\mathbf{a}(\\theta)}{\\mathbf{a}^H(\\theta) \\mathbf{R}_l^{-1} \\mathbf{a}(\\theta)}$$

    where $\\mathbf{R}_l = \\mathbf{R} + \\delta \\mathbf{I}$ and $\\delta$ = diagonal_loading.

References:
    - Capon, J. (1969). "High-resolution frequency-wavenumber spectrum analysis."
      Proc. IEEE, 57(8), 1408-1418.
    - Van Trees, H.L. (2002). "Optimum Array Processing." Wiley.
"""

from __future__ import annotations

from math import radians, sin
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _mvdr(data: np.ndarray, steering_vec: np.ndarray) -> np.ndarray:
    n_samples = data.shape[1]
    r = (data @ data.conj().T) / n_samples
    r_inv = np.linalg.inv(r)
    a = steering_vec
    numerator = r_inv @ a
    denominator = a.conj() @ numerator
    w = numerator / denominator
    y = w.conj() @ data
    return np.real(y)


class BeamformerMVDR(Knot):
    """Apply an MVDR (Capon) beamformer with optional diagonal loading for robustness."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: Knot | int,
        steering_angle_deg: Knot | float,
        diagonal_loading: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_elements=num_elements,
            steering_angle_deg=steering_angle_deg,
            diagonal_loading=diagonal_loading,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        num_elements: int,
        element_spacing_m: float,
        steering_angle_deg: float,
        diagonal_loading: float = 0.0,
        **_: Any,
    ) -> SignalPayload:
        """Apply the MVDR beamformer and return the beamformed SignalFrame.

        Args:
            signal: The multi-element array input signal payload.
            num_elements: Number of array elements (positive integer).
            element_spacing_m: Distance between adjacent elements in metres (positive float).
            steering_angle_deg: Steering direction in degrees (float).
            diagonal_loading: Non-negative loading constant for robustness.

        Returns:
            Single-channel SignalPayload representing the MVDR beamformed output.

        Raises:
            ValueError: If num_elements or diagonal_loading are invalid.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMVDR: num_elements must be a positive integer")
        if not isinstance(element_spacing_m, (int, float)) or element_spacing_m <= 0:
            raise ValueError("BeamformerMVDR: element_spacing_m must be a positive scalar")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("BeamformerMVDR: steering_angle_deg must be a float")
        if not isinstance(diagonal_loading, (int, float)) or diagonal_loading < 0.0:
            raise ValueError("BeamformerMVDR: diagonal_loading must be >= 0.0")

        import asyncio

        c = 343.0
        sample_rate_hz = signal.frame.sample_rate_hz
        f0 = sample_rate_hz / 4.0
        theta = radians(steering_angle_deg)
        d = float(element_spacing_m)
        a = np.array(
            [np.exp(-1j * 2 * np.pi * f0 * i * d * sin(theta) / c) for i in range(num_elements)],
            dtype=complex,
        )
        data = signal.data.astype(complex)
        if diagonal_loading > 0.0:
            n_samples = data.shape[1]
            r = (data @ data.conj().T) / n_samples
            r = r + diagonal_loading * np.eye(num_elements)
            r_inv = np.linalg.inv(r)
            numerator = r_inv @ a
            denominator = a.conj() @ numerator
            w = numerator / denominator
            beamformed = np.real(w.conj() @ data)
        else:
            beamformed = await asyncio.to_thread(_mvdr, data, a)
        return SignalPayload(
            frame=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:mvdr",
                channel_count=1,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=signal.frame.samples_per_channel,
            ),
            data=beamformed[np.newaxis, :],
        )
