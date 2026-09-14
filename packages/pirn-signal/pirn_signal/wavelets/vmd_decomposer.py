"""``VMDDecomposer`` — variational mode decomposition.

Algorithm:
    1. Receive the input signal frame, mode_count, bandwidth_constraint, and backend.
    2. Validate mode_count (positive integer), bandwidth_constraint (positive float),
       and backend (one of ``"vmdpy"``, ``"numpy"``).
    3. Formulate the constrained optimisation: decompose the signal into mode_count
       band-limited modes each centred at an adaptive centre frequency.
    4. Solve via ADMM (alternating direction method of multipliers) in the frequency
       domain, using the selected backend:

       - ``"vmdpy"`` (default): the reference ADMM solver from the ``vmdpy`` package.
       - ``"numpy"``: a simplified frequency-domain gradient-descent approximation
         implemented directly against ``numpy.fft``, for environments where
         ``vmdpy`` cannot be installed. Its results are not numerically identical
         to ``vmdpy``'s and it should be treated as an approximation, not a
         drop-in replacement.
    5. Iterate until convergence: update modes, centre frequencies, and Lagrange multipliers.
    6. Return a WaveletPayload with mode_count IMF-like modes.

    The backend is an explicit input rather than an availability probe: which
    backend ran is always recorded in the pipeline's lineage, and requesting
    ``"vmdpy"`` without it installed raises ``ImportError`` instead of silently
    falling back to a numerically different implementation.

Math:
    VMD optimisation problem:

    $$\\min_{u_k, \\omega_k} \\sum_k \\|\\partial_t [(\\delta(t) + j/\\pi t) * u_k(t)] e^{-j\\omega_k t}\\|_2^2$$

    $$\\text{s.t.} \\quad \\sum_k u_k = f$$

References:
    [1] Dragomiretskiy, K. & Zosso, D. (2014). "Variational mode decomposition."
        IEEE Trans. Signal Process., 62(3), 531-544.
    [2] vmdpy (backend="vmdpy", the reference ADMM implementation):
        https://github.com/vrcarva/vmdpy
    [3] backend="numpy": a simplified frequency-domain gradient-descent
        approximation of the same optimisation problem, implemented locally
        against numpy.fft for environments without vmdpy. Chosen only as a
        fallback; prefer "vmdpy" whenever it can be installed.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.vmdpy_binding import VmdpyBinding
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


class VMDDecomposer(Knot):
    """Variational mode decomposition."""

    _valid_backends: ClassVar[frozenset[str]] = frozenset({"vmdpy", "numpy"})

    def __init__(
        self,
        *,
        signal: Knot,
        mode_count: Knot | int,
        bandwidth_constraint: Knot | float,
        backend: Knot | str = "vmdpy",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            mode_count=mode_count,
            bandwidth_constraint=bandwidth_constraint,
            backend=backend,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        mode_count: int,
        bandwidth_constraint: float,
        backend: str = "vmdpy",
        **_: Any,
    ) -> WaveletPayload:
        """Decompose the signal into band-limited modes via variational mode decomposition.

        Args:
            signal: Signal payload to decompose.
            mode_count: Number of VMD modes to extract (positive integer).
            bandwidth_constraint: Bandwidth penalty parameter alpha (positive float).
            backend: VMD solver to use — ``"vmdpy"`` (default, the reference ADMM
                implementation) or ``"numpy"`` (a simplified fallback that needs no
                optional dependency).

        Returns:
            WaveletPayload of VMD modes.

        Raises:
            ValueError: If mode_count, bandwidth_constraint, or backend are invalid.
            ImportError: If backend="vmdpy" is selected but ``vmdpy`` is not installed.
        """
        if not isinstance(mode_count, int) or mode_count <= 0:
            raise ValueError("VMDDecomposer: mode_count must be a positive integer")
        if not isinstance(bandwidth_constraint, (int, float)) or bandwidth_constraint <= 0:
            raise ValueError("VMDDecomposer: bandwidth_constraint must be positive")
        if backend not in VMDDecomposer._valid_backends:
            raise ValueError(
                "VMDDecomposer: backend must be one of "
                f"{sorted(VMDDecomposer._valid_backends)}, got {backend!r}"
            )
        modes = await asyncio.to_thread(
            VMDDecomposer._run_vmd, signal.data, float(bandwidth_constraint), mode_count, backend
        )
        frame = WaveletFrame(
            signal_id=signal.metadata.signal_id,
            wavelet_name="vmd",
            scale_count=len(modes),
        )
        return WaveletPayload(metadata=frame, data=modes)

    @staticmethod
    def _run_vmd(data: np.ndarray, alpha: float, mode_count: int, backend: str) -> list[np.ndarray]:
        if data.ndim == 2:
            all_modes: list[np.ndarray] = []
            for ch_idx in range(data.shape[0]):
                modes = VMDDecomposer._run_vmd(data[ch_idx], alpha, mode_count, backend)
                all_modes.extend(modes)
            return all_modes
        if backend == "vmdpy":
            modes = VMDDecomposer._run_vmd_vmdpy(data, alpha, mode_count)
        else:
            modes = VMDDecomposer._vmd_numpy(data, alpha, mode_count)
        return [modes[mode_idx] for mode_idx in range(modes.shape[0])]

    @staticmethod
    def _run_vmd_vmdpy(signal_array: np.ndarray, alpha: float, mode_count: int) -> np.ndarray:
        vmdpy = VmdpyBinding.load()
        return vmdpy.vmd(signal_array, alpha, mode_count)

    @staticmethod
    def _vmd_numpy(
        signal_array: np.ndarray, alpha: float, mode_count: int, max_iter: int = 50
    ) -> np.ndarray:
        """Simplified frequency-domain VMD via gradient descent (backend="numpy")."""
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
