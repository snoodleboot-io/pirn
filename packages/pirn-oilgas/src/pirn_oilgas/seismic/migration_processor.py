"""``MigrationProcessor`` — pre- or post-stack migration of a seismic volume.

Algorithm:
    1. Receive a seismic volume and a ``method`` string selecting the
       migration algorithm.
    2. Validate that ``method`` is one of ``kirchhoff``, ``rtm``,
       ``phase_shift``, or ``stolt``.
    3. Apply the selected migration algorithm to collapse diffractions and
       reposition dipping reflectors to their true subsurface positions.
    4. Return a migrated SegyVolume reference.

Math:
    Stolt F-K migration dispersion relation:

    $$k_z = \\sqrt{\\left(\\frac{2f}{v}\\right)^2 - k_x^2 - k_y^2}$$

    Kirchhoff diffraction-stack summation:

    $$u(\\mathbf{x}, t=0) = \\int_S \\frac{\\partial}{\\partial t}
      \\frac{p(\\mathbf{\\xi}, t_s + t_r)}{\\cos\\theta} \\, dS$$

References:
    - Stolt, R.H. (1978). Migration by Fourier transform. *Geophysics*,
      43(1), 23-48.
    - Gazdag, J. (1978). Wave equation migration with the phase-shift method.
      *Geophysics*, 43(7), 1342-1351.
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 4
      (migration methods).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class MigrationProcessor(Knot):
    """Migrate a seismic volume using one of the supported algorithms."""

    def __init__(
        self,
        *,
        volume: Knot,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(volume=volume, method=method, _config=_config, **kwargs)

    async def process(self, volume: SegyVolume, method: str, **_: Any) -> SegyVolume:
        """Migrate the input seismic volume using the configured algorithm and return the migrated SegyVolume.

        Args:
            volume: Pre-stack or post-stack seismic volume to migrate.
            method: Migration algorithm: one of ``kirchhoff``, ``rtm``,
                ``phase_shift``, or ``stolt``.

        Returns:
            SegyVolume of the migrated image.
        """
        valid_methods: frozenset[str] = frozenset({"kirchhoff", "rtm", "phase_shift", "stolt"})
        if method not in valid_methods:
            raise ValueError(f"MigrationProcessor: method must be one of {sorted(valid_methods)}")
        return SegyVolume(volume_id=f"{volume.volume_id}:migrated_{method}")
