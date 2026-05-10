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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload

_frame_size = 512
_hop_size = 256
_spectral_floor = 0.002


def _spectral_gate(x: np.ndarray, noise_estimate_frames: int, alpha: float) -> np.ndarray:
    """Apply spectral gating via overlap-add STFT frames."""
    n = len(x)
    num_frames = max(1, (n - _frame_size) // _hop_size + 1)
    window = np.hanning(_frame_size)

    frames = np.array(
        [
            x[i * _hop_size : i * _hop_size + _frame_size] * window
            for i in range(num_frames)
            if i * _hop_size + _frame_size <= n
        ]
    )
    if frames.ndim == 1 or len(frames) == 0:
        return x

    spectra = np.fft.rfft(frames, axis=1)
    magnitudes = np.abs(spectra)
    phases = np.angle(spectra)

    noise_frames = min(noise_estimate_frames, len(frames))
    noise_floor = np.mean(magnitudes[:noise_frames], axis=0)

    cleaned_mag = np.maximum(
        magnitudes - alpha * noise_floor,
        _spectral_floor * magnitudes,
    )
    cleaned_spectra = cleaned_mag * np.exp(1j * phases)
    cleaned_frames = np.fft.irfft(cleaned_spectra, n=_frame_size, axis=1)

    out = np.zeros(n, dtype=np.float32)
    norm = np.zeros(n, dtype=np.float32)
    for i, frame in enumerate(cleaned_frames):
        start = i * _hop_size
        end = start + _frame_size
        out[start:end] += frame * window
        norm[start:end] += window**2

    nz = norm > 1e-8
    out[nz] /= norm[nz]
    return out


def _denoise_signal(data: np.ndarray, noise_estimate_frames: int, alpha: float) -> np.ndarray:
    if data.ndim == 1:
        return _spectral_gate(data, noise_estimate_frames, alpha)
    return np.stack([_spectral_gate(ch, noise_estimate_frames, alpha) for ch in data])


class AudioDenoiser(Knot):
    """Spectral-subtraction noise reduction for audio signals."""

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
        signal: SignalPayload,
        noise_estimate_frames: int,
        over_subtraction_factor: float,
        **_: Any,
    ) -> SignalPayload:
        """Apply spectral subtraction to reduce background noise.

        Args:
            signal: Noisy audio signal to denoise.
            noise_estimate_frames: Number of initial frames used to estimate the noise spectrum
                (positive integer).
            over_subtraction_factor: Multiplier on the noise estimate (>= 1.0).

        Returns:
            SignalPayload with reduced background noise.

        Raises:
            ValueError: If noise_estimate_frames or over_subtraction_factor are invalid.
        """
        if not isinstance(noise_estimate_frames, int) or noise_estimate_frames <= 0:
            raise ValueError("AudioDenoiser: noise_estimate_frames must be a positive integer")
        if not isinstance(over_subtraction_factor, (int, float)) or over_subtraction_factor < 1.0:
            raise ValueError("AudioDenoiser: over_subtraction_factor must be >= 1.0")
        result = await asyncio.to_thread(
            _denoise_signal, signal.data, noise_estimate_frames, float(over_subtraction_factor)
        )
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:denoised",
                channel_count=signal.frame.channel_count,
                sample_rate_hz=signal.frame.sample_rate_hz,
                samples_per_channel=result.shape[-1],
            ),
            data=np.asarray(result),
        )
