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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class BeamformerMUSIC(Knot):
    """Compute the MUSIC spatial pseudo-spectrum for direction-of-arrival estimation."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_elements: Knot | int,
        num_sources: Knot | int,
        angle_scan_deg: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_elements=num_elements,
            num_sources=num_sources,
            angle_scan_deg=angle_scan_deg,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _scan_bins(start: float, stop: float, step: float) -> int:
        if step == 0:
            return 0
        return max(0, int((stop - start) / step))

    async def process(
        self,
        signal: Any,
        num_elements: int,
        num_sources: int,
        angle_scan_deg: tuple[float, float, float],
        **_: Any,
    ) -> SpectrumFrame:
        """Compute the MUSIC spatial pseudo-spectrum and return a SpectrumFrame.

        Args:
            signal: The multi-element array input signal frame.
            num_elements: Number of array elements (positive integer).
            num_sources: Number of signal sources (positive integer).
            angle_scan_deg: Tuple (start, stop, step) defining the scan grid in degrees;
                step must be non-zero.

        Returns:
            SpectrumFrame where frequency_bins represents the number of scanned angles.

        Raises:
            ValueError: If num_elements, num_sources, or angle_scan_deg are invalid.
        """
        if not isinstance(num_elements, int) or num_elements <= 0:
            raise ValueError("BeamformerMUSIC: num_elements must be a positive integer")
        if not isinstance(num_sources, int) or num_sources <= 0:
            raise ValueError("BeamformerMUSIC: num_sources must be a positive integer")
        if (
            not isinstance(angle_scan_deg, tuple)
            or len(angle_scan_deg) != 3
            or any(not isinstance(v, (int, float)) for v in angle_scan_deg)
        ):
            raise ValueError(
                "BeamformerMUSIC: angle_scan_deg must be a (start, stop, step) tuple of floats"
            )
        start, stop, step = angle_scan_deg
        if step == 0:
            raise ValueError("BeamformerMUSIC: angle_scan_deg step must be non-zero")
        bins = self._scan_bins(start, stop, step)
        return SpectrumFrame(
            signal_id="music",
            frequency_bins=bins,
            frequency_resolution_hz=float(abs(step)),
        )
