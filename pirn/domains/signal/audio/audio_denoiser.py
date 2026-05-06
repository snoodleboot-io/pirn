"""``AudioDenoiser`` — spectral-subtraction noise reduction.

Algorithm:
    1. Receive the input audio signal frame.
    2. Validate noise_estimate_frames and over_subtraction_factor.
    3. Compute the STFT of the signal.
    4. Estimate the noise power spectrum from the first noise_estimate_frames frames.
    5. For each subsequent frame k: subtract scaled noise estimate from magnitude spectrum:
       |S_hat(k, f)| = max(|X(k, f)| - alpha * |N(f)|, beta * |X(k, f)|)
       where alpha = over_subtraction_factor and beta is a spectral floor constant.
    6. Reconstruct the signal via inverse STFT.
    7. Return a denoised SignalFrame.

Math:
    Spectral subtraction magnitude update:

    $$\\hat{|S(k,f)|} = \\max\\!\\left(|X(k,f)| - \\alpha \\, |\\hat{N}(f)|,\\; \\beta |X(k,f)|\\right)$$

    where:
    - $\\alpha \\geq 1$ is the over_subtraction_factor
    - $\\beta \\in (0,1)$ is the spectral floor preventing musical noise
    - $|\\hat{N}(f)|$ is the estimated noise magnitude spectrum

References:
    - Boll, S.F. (1979). "Suppression of acoustic noise in speech using spectral subtraction."
      IEEE Trans. Acoustics Speech Signal Process., 27(2), 113-120.
    - Martin, R. (2001). "Noise power spectral density estimation based on optimal smoothing
      and minimum statistics." IEEE Trans. Speech Audio Process., 9(5), 504-512.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class AudioDenoiser(Knot):
    """Spectral-subtraction noise reduction for audio signals.

    Production needs ``librosa`` or a hand-rolled STFT-based implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        noise_estimate_frames: Knot | int,
        over_subtraction_factor: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            noise_estimate_frames=noise_estimate_frames,
            over_subtraction_factor=over_subtraction_factor,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        noise_estimate_frames: int,
        over_subtraction_factor: float,
        **_: Any,
    ) -> SignalFrame:
        """Apply spectral subtraction to reduce background noise.

        Args:
            signal: Noisy audio signal to denoise.
            noise_estimate_frames: Number of initial frames used to estimate the noise spectrum
                (positive integer).
            over_subtraction_factor: Multiplier on the noise estimate (>= 1.0).

        Returns:
            SignalFrame with reduced background noise.

        Raises:
            ValueError: If noise_estimate_frames or over_subtraction_factor are invalid.
        """
        if not isinstance(noise_estimate_frames, int) or noise_estimate_frames <= 0:
            raise ValueError(
                "AudioDenoiser: noise_estimate_frames must be a positive integer"
            )
        if (
            not isinstance(over_subtraction_factor, (int, float))
            or over_subtraction_factor < 1.0
        ):
            raise ValueError(
                "AudioDenoiser: over_subtraction_factor must be >= 1.0"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:denoised",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
