# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``BeamformerMVDR`` — minimum variance distortionless response beamformer.

Algorithm:
    1. Receive the multi-element array signal frame and configuration parameters.
    2. Validate num_elements, element_spacing_m (positive float), steering_angle_deg
       (float), diagonal_loading (>= 0), and speed_of_sound (positive float).
    3. Build a narrowband steering vector a(theta) at a single reference frequency
       f0 = sample_rate_hz / 4 (a simplifying narrowband assumption: MVDR is
       formulated for a single carrier/subband, so the broadband array data is
       steered as if it were narrowband at f0 rather than per-frequency-bin).
    4. Compute the sample covariance matrix R = (1/N) X X^H.
    5. Apply diagonal loading: R_l = R + diagonal_loading * I (a no-op when
       diagonal_loading is 0).
    6. Compute MVDR weights: w = R_l^{-1} a / (a^H R_l^{-1} a).
    7. Apply weights to the array signal: y = w^H X.
    8. Return a single-channel beamformed SignalPayload.

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

import asyncio
from math import radians, sin
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload


class BeamformerMVDR(Knot):
    """Apply an MVDR (Capon) beamformer with optional diagonal loading for robustness."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: Knot | int,
        element_spacing_m: Knot | float,
        steering_angle_deg: Knot | float,
        diagonal_loading: Knot | float = 0.0,
        speed_of_sound: Knot | float = 343.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_elements=num_elements,
            element_spacing_m=element_spacing_m,
            steering_angle_deg=steering_angle_deg,
            diagonal_loading=diagonal_loading,
            speed_of_sound=speed_of_sound,
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
        speed_of_sound: float = 343.0,
        **_: Any,
    ) -> SignalPayload:
        """Apply the MVDR beamformer and return the beamformed SignalPayload.

        Args:
            signal: The multi-element array input signal payload.
            num_elements: Number of array elements (positive integer).
            element_spacing_m: Distance between adjacent elements in metres (positive float).
            steering_angle_deg: Steering direction in degrees (float).
            diagonal_loading: Non-negative loading constant for robustness.
            speed_of_sound: Propagation speed in m/s (positive float, default 343.0
                for sound in air at ~20°C).

        Returns:
            Single-channel SignalPayload representing the MVDR beamformed output.

        Raises:
            ValueError: If num_elements, element_spacing_m, diagonal_loading, or
                speed_of_sound are invalid.
            TypeError: If steering_angle_deg is not a float.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMVDR: num_elements must be a positive integer")
        if not isinstance(element_spacing_m, (int, float)) or element_spacing_m <= 0:
            raise ValueError("BeamformerMVDR: element_spacing_m must be a positive scalar")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("BeamformerMVDR: steering_angle_deg must be a float")
        if not isinstance(diagonal_loading, (int, float)) or diagonal_loading < 0.0:
            raise ValueError("BeamformerMVDR: diagonal_loading must be >= 0.0")
        if not isinstance(speed_of_sound, (int, float)) or speed_of_sound <= 0:
            raise ValueError("BeamformerMVDR: speed_of_sound must be a positive scalar")

        sample_rate_hz = signal.frame.sample_rate_hz
        f0 = sample_rate_hz / 4.0
        theta = radians(steering_angle_deg)
        steering_vec = BeamformerMVDR._steering_vector(
            num_elements, f0, float(element_spacing_m), theta, float(speed_of_sound)
        )
        data = signal.data.astype(complex)
        beamformed = await asyncio.to_thread(
            BeamformerMVDR._mvdr, data, steering_vec, float(diagonal_loading)
        )
        return signal.derive(
            "mvdr",
            beamformed[np.newaxis, :],
            channel_count=1,
        )

    @staticmethod
    def _steering_vector(
        num_elements: int,
        frequency_hz: float,
        element_spacing_m: float,
        steering_angle_rad: float,
        speed_of_sound: float,
    ) -> np.ndarray:
        """Narrowband far-field steering vector for a uniform linear array."""
        return np.array(
            [
                np.exp(
                    -1j
                    * 2
                    * np.pi
                    * frequency_hz
                    * element_index
                    * element_spacing_m
                    * sin(steering_angle_rad)
                    / speed_of_sound
                )
                for element_index in range(num_elements)
            ],
            dtype=complex,
        )

    @staticmethod
    def _mvdr(data: np.ndarray, steering_vec: np.ndarray, diagonal_loading: float) -> np.ndarray:
        """Compute MVDR weights (with optional diagonal loading, a no-op at 0.0) and apply them."""
        n_samples = data.shape[1]
        covariance_matrix = (data @ data.conj().T) / n_samples
        covariance_matrix = covariance_matrix + diagonal_loading * np.eye(data.shape[0])
        r_inv = np.linalg.inv(covariance_matrix)
        numerator = r_inv @ steering_vec
        denominator = steering_vec.conj() @ numerator
        beamform_weights = numerator / denominator
        beamformed = beamform_weights.conj() @ data
        return np.real(beamformed)
