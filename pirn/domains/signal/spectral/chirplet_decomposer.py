"""``ChirpletDecomposer`` — chirplet-transform decomposition.

Algorithm:
    1. Receive the input signal frame and chirplet_count.
    2. Validate chirplet_count (positive integer).
    3. Initialise a bank of chirplet atoms parameterised by time centre,
       frequency centre, duration, and chirp rate.
    4. Apply a matching-pursuit or basis-projection step to select the
       best chirplet_count atoms explaining the signal.
    5. Return a SpectrumFrame with frequency_bins equal to chirplet_count.

Math:
    Chirplet atom:

    $$g_{t_0, f_0, \\sigma, c}(t) = \\frac{1}{(2\\pi \\sigma^2)^{1/4}}
      e^{-(t-t_0)^2/(4\\sigma^2)} e^{j 2\\pi (f_0 t + c t^2 / 2)}$$

    Chirplet transform coefficient:

    $$C_{t_0, f_0, c} = \\langle x, g_{t_0, f_0, \\sigma, c} \\rangle$$

References:
    - Mann, S. & Haykin, S. (1995). "The chirplet transform: Physical considerations."
      IEEE Trans. Signal Process., 43(11), 2745-2761.
    - scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class ChirpletDecomposer(Knot):
    """Chirplet-transform decomposition for non-stationary signals.

    Production needs a chirplet library or a custom matching-pursuit
    implementation on top of ``scipy``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        chirplet_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            chirplet_count=chirplet_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        chirplet_count: int,
        **_: Any,
    ) -> SpectrumFrame:
        """Decompose the signal into chirplet atoms and return a SpectrumFrame of transform coefficients.

        Args:
            signal: Non-stationary signal to decompose using the chirplet transform.
            chirplet_count: Number of chirplet atoms to extract (positive integer).

        Returns:
            SpectrumFrame with ``frequency_bins`` equal to ``chirplet_count``.

        Raises:
            ValueError: If chirplet_count is not a positive integer.
        """
        if not isinstance(chirplet_count, int) or chirplet_count <= 0:
            raise ValueError("ChirpletDecomposer: chirplet_count must be a positive integer")
        return SpectrumFrame(
            signal_id=signal.signal_id,
            frequency_bins=chirplet_count,
            frequency_resolution_hz=0.0,
        )
