"""``BeamformerMUSIC`` — MUSIC spatial spectrum beamformer."""

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
        num_elements: int,
        num_sources: int,
        angle_scan_deg: tuple[float, float, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._num_elements = num_elements
        self._num_sources = num_sources
        self._angle_scan_deg = angle_scan_deg
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def num_elements(self) -> int:
        return self._num_elements

    @staticmethod
    def _scan_bins(start: float, stop: float, step: float) -> int:
        if step == 0:
            return 0
        return max(0, int((stop - start) / step))

    async def process(self, signal: Any, **_: Any) -> SpectrumFrame:
        """Compute the MUSIC spatial pseudo-spectrum and return a SpectrumFrame.

        Args:
            signal: The multi-element array input signal frame.

        Returns:
            SpectrumFrame where frequency_bins represents the number of scanned angles.
        """
        start, stop, step = self._angle_scan_deg
        bins = self._scan_bins(start, stop, step)
        return SpectrumFrame(
            signal_id="music",
            frequency_bins=bins,
            frequency_resolution_hz=float(abs(step)),
        )
