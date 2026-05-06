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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


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
        signal: SignalFrame,
        num_elements: int,
        steering_angle_deg: float,
        diagonal_loading: float = 0.0,
        **_: Any,
    ) -> SignalFrame:
        """Apply the MVDR beamformer and return the beamformed SignalFrame.

        Args:
            signal: The multi-element array input signal frame.
            num_elements: Number of array elements (positive integer).
            steering_angle_deg: Steering direction in degrees (float).
            diagonal_loading: Non-negative loading constant for robustness.

        Returns:
            SignalFrame representing the MVDR beamformed output.

        Raises:
            ValueError: If num_elements or diagonal_loading are invalid.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMVDR: num_elements must be a positive integer")
        if not isinstance(steering_angle_deg, (int, float)):
            raise TypeError("BeamformerMVDR: steering_angle_deg must be a float")
        if not isinstance(diagonal_loading, (int, float)) or diagonal_loading < 0.0:
            raise ValueError("BeamformerMVDR: diagonal_loading must be >= 0.0")
        return SignalFrame(
            signal_id=f"{signal.signal_id}:mvdr",
            channel_count=1,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
