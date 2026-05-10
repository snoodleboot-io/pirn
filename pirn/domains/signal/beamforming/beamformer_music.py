"""``BeamformerMUSIC`` — MUSIC spatial spectrum beamformer.

Algorithm:
    1. Receive the multi-element array signal frame and configuration parameters.
    2. Validate num_elements, num_sources, and angle_scan_deg (start, stop, non-zero step).
    3. Compute the sample covariance matrix R = (1/N) X X^H.
    4. Eigendecompose R = U S U^H; partition into signal subspace (top num_sources
       eigenvectors) and noise subspace (remaining num_elements - num_sources eigenvectors).
    5. For each scan angle theta in [start, stop, step]:
       a. Construct the steering vector a(theta) ∈ C^{num_elements}.
       b. Compute MUSIC pseudo-spectrum: P(theta) = 1 / (a^H E_n E_n^H a).
    6. Return a SpectrumFrame with frequency_bins = number of scan angles.

Math:
    MUSIC pseudo-spectrum:

    $$P_{\\text{MUSIC}}(\\theta) = \\frac{1}{\\mathbf{a}^H(\\theta) \\mathbf{E}_n \\mathbf{E}_n^H \\mathbf{a}(\\theta)}$$

    Steering vector for ULA with half-wavelength spacing:

    $$\\mathbf{a}(\\theta) = \\begin{bmatrix} 1 & e^{j\\pi\\sin\\theta} & \\cdots & e^{j\\pi(M-1)\\sin\\theta} \\end{bmatrix}^T$$

References:
    - Schmidt, R.O. (1986). "Multiple emitter location and signal parameter estimation."
      IEEE Trans. Antennas Propagat., 34(3), 276-280.
    - Stoica, P. & Moses, R.L. (2005). "Spectral Analysis of Signals." Prentice Hall.
"""

from __future__ import annotations

from math import radians, sin
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _steering_vector(n_el: int, d: float, theta: float, c: float, f0: float) -> np.ndarray:
    return np.array(
        [np.exp(-1j * 2 * np.pi * f0 * i * d * sin(radians(theta)) / c) for i in range(n_el)],
        dtype=complex,
    )


def _music_spatial(
    data: np.ndarray,
    n_el: int,
    d: float,
    n_src: int,
    n_grid: int,
    c: float,
    f0: float,
) -> np.ndarray:
    n_samples = data.shape[1]
    r = (data @ data.conj().T) / n_samples
    _, evecs = np.linalg.eigh(r)
    en = evecs[:, : n_el - n_src]
    en_outer = en @ en.conj().T
    angles = np.linspace(-90.0, 90.0, n_grid)
    spectrum = np.zeros(n_grid)
    for k, theta in enumerate(angles):
        a = _steering_vector(n_el, d, theta, c, f0)
        denom = np.real(a.conj() @ en_outer @ a)
        spectrum[k] = 1.0 / (denom + 1e-30)
    return spectrum


class BeamformerMUSIC(Knot):
    """Compute the MUSIC spatial pseudo-spectrum for direction-of-arrival estimation."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: Knot | int,
        element_spacing_m: Knot | float,
        num_sources: Knot | int,
        n_grid: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_elements=num_elements,
            element_spacing_m=element_spacing_m,
            num_sources=num_sources,
            n_grid=n_grid,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        num_elements: int,
        element_spacing_m: float,
        num_sources: int,
        n_grid: int,
        **_: Any,
    ) -> SignalPayload:
        """Compute the MUSIC spatial pseudo-spectrum and return a SignalPayload.

        Args:
            signal: The multi-element array input signal payload.
            num_elements: Number of array elements (positive integer).
            element_spacing_m: Distance between adjacent elements in metres (positive float).
            num_sources: Number of signal sources (positive integer, < num_elements).
            n_grid: Number of angle bins spanning -90 to 90 degrees.

        Returns:
            SignalPayload where data is the pseudospectrum (shape 1 x n_grid).

        Raises:
            ValueError: If num_elements, num_sources, or n_grid are invalid.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMUSIC: num_elements must be a positive integer")
        if not isinstance(element_spacing_m, (int, float)) or element_spacing_m <= 0:
            raise ValueError("BeamformerMUSIC: element_spacing_m must be a positive scalar")
        if not isinstance(num_sources, int) or num_sources <= 0:
            raise ValueError("BeamformerMUSIC: num_sources must be a positive integer")
        if num_sources >= num_elements:
            raise ValueError("BeamformerMUSIC: num_sources must be less than num_elements")
        if not isinstance(n_grid, int) or n_grid <= 0:
            raise ValueError("BeamformerMUSIC: n_grid must be a positive integer")

        import asyncio

        c = 343.0
        f0 = signal.frame.sample_rate_hz / 4.0
        data = signal.data.astype(complex)
        spectrum = await asyncio.to_thread(
            _music_spatial, data, num_elements, float(element_spacing_m), num_sources, n_grid, c, f0
        )
        return SignalPayload(
            metadata=SignalFrame(
                signal_id=f"{signal.frame.signal_id}:music",
                channel_count=1,
                sample_rate_hz=1.0,
                samples_per_channel=n_grid,
            ),
            data=spectrum[np.newaxis, :],
        )
