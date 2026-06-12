"""``VMDDecomposer`` — variational mode decomposition.

Algorithm:
    1. Receive the input signal frame, mode_count, and bandwidth_constraint.
    2. Validate mode_count (positive integer) and bandwidth_constraint (positive float).
    3. Formulate the constrained optimisation: decompose the signal into mode_count
       band-limited modes each centred at an adaptive centre frequency.
    4. Solve via ADMM (alternating direction method of multipliers) in the frequency domain.
    5. Iterate until convergence: update modes, centre frequencies, and Lagrange multipliers.
    6. Return a WaveletFrame with mode_count IMF-like modes.

Math:
    VMD optimisation problem:

    $$\\min_{u_k, \\omega_k} \\sum_k \\|\\partial_t [(\\delta(t) + j/\\pi t) * u_k(t)] e^{-j\\omega_k t}\\|_2^2$$

    $$\\text{s.t.} \\quad \\sum_k u_k = f$$

References:
    - Dragomiretskiy, K. & Zosso, D. (2014). "Variational mode decomposition."
      IEEE Trans. Signal Process., 62(3), 531-544.
    - vmdpy: https://github.com/vrcarva/vmdpy
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.types.wavelet_payload import WaveletPayload

try:
    from vmdpy import VMD as _vmdpy_vmd

    _VMDPY_AVAILABLE = True
except ImportError:
    _VMDPY_AVAILABLE = False


def _vmd_numpy(
    signal_array: np.ndarray, alpha: float, mode_count: int, max_iter: int = 50
) -> np.ndarray:
    """Simplified frequency-domain VMD via gradient descent (fallback when vmdpy unavailable)."""
    signal_length = len(signal_array)
    f_hat = np.fft.fftshift(np.fft.fft(signal_array))
    omega = np.fft.fftshift(np.fft.fftfreq(signal_length))
    omega_k = np.linspace(0, 0.5, mode_count)
    u_hat = np.zeros((mode_count, signal_length), dtype=complex)
    lambda_hat = np.zeros(signal_length, dtype=complex)
    for _ in range(max_iter):
        for mode_idx in range(mode_count):
            u_hat_sum = np.sum(u_hat, axis=0) - u_hat[mode_idx]
            numerator = f_hat - u_hat_sum - lambda_hat / 2.0
            denominator = 1.0 + 2.0 * alpha * (omega - omega_k[mode_idx]) ** 2
            u_hat[mode_idx] = numerator / denominator
        for mode_idx in range(mode_count):
            positive_mask = omega > 0
            weighted = np.where(positive_mask, omega * np.abs(u_hat[mode_idx]) ** 2, 0.0)
            total = np.sum(np.where(positive_mask, np.abs(u_hat[mode_idx]) ** 2, 0.0))
            omega_k[mode_idx] = np.sum(weighted) / (total + 1e-10)
        lambda_hat += f_hat - np.sum(u_hat, axis=0)
    modes = np.real(np.fft.ifft(np.fft.ifftshift(u_hat, axes=-1), axis=-1))
    return modes


def _run_vmd_vmdpy(signal_array: np.ndarray, alpha: float, mode_count: int) -> np.ndarray:
    u, _u_hat, _omega = _vmdpy_vmd(signal_array, alpha, tau=0, K=mode_count, DC=0, init=1, tol=1e-7)  # type: ignore[possibly-unbound]
    return u


def _run_vmd(data: np.ndarray, alpha: float, mode_count: int) -> list[np.ndarray]:
    if data.ndim == 2:
        all_modes: list[np.ndarray] = []
        for ch_idx in range(data.shape[0]):
            modes = _run_vmd(data[ch_idx], alpha, mode_count)
            all_modes.extend(modes)
        return all_modes
    if _VMDPY_AVAILABLE:
        modes = _run_vmd_vmdpy(data, alpha, mode_count)
    else:
        modes = _vmd_numpy(data, alpha, mode_count)
    return [modes[mode_idx] for mode_idx in range(modes.shape[0])]


class VMDDecomposer(Knot):
    """Variational mode decomposition."""

    def __init__(
        self,
        *,
        signal: Knot,
        mode_count: Knot | int,
        bandwidth_constraint: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            mode_count=mode_count,
            bandwidth_constraint=bandwidth_constraint,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        mode_count: int,
        bandwidth_constraint: float,
        **_: Any,
    ) -> WaveletPayload:
        """Decompose the signal into band-limited modes via variational mode decomposition.

        Args:
            signal: Signal payload to decompose.
            mode_count: Number of VMD modes to extract (positive integer).
            bandwidth_constraint: Bandwidth penalty parameter alpha (positive float).

        Returns:
            WaveletPayload of VMD modes.

        Raises:
            ValueError: If mode_count or bandwidth_constraint are invalid.
        """
        if not isinstance(mode_count, int) or mode_count <= 0:
            raise ValueError("VMDDecomposer: mode_count must be a positive integer")
        if not isinstance(bandwidth_constraint, (int, float)) or bandwidth_constraint <= 0:
            raise ValueError("VMDDecomposer: bandwidth_constraint must be positive")
        modes = await asyncio.to_thread(
            _run_vmd, signal.data, float(bandwidth_constraint), mode_count
        )
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name="vmd",
            scale_count=len(modes),
        )
        return WaveletPayload(metadata=frame, data=modes)
