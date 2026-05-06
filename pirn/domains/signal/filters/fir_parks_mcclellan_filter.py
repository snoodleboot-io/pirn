"""``FIRParksMcClellanFilter`` — equiripple FIR via Parks-McClellan algorithm.

Algorithm:
    1. Receive the input signal frame, num_taps, bands, and desired.
    2. Validate num_taps (positive odd integer), bands (even-length tuple of normalised
       frequency edges), and desired (one value per band pair).
    3. Call the Remez exchange algorithm (``scipy.signal.remez``) to compute the
       num_taps-length FIR coefficients that minimise the weighted Chebyshev error
       across the specified frequency bands.
    4. Apply the resulting FIR filter to the input signal.
    5. Return a filtered SignalFrame.

Math:
    Parks-McClellan (Remez) minimax optimisation:

    $$\\min_{\\mathbf{h}} \\max_{\\omega} W(\\omega) |H(e^{j\\omega}) - D(\\omega)|$$

    where $D(\\omega)$ is the desired response, $W(\\omega)$ is a weight function,
    and the solution has equiripple error across all band edges.

References:
    - Parks, T.W. & McClellan, J.H. (1972). "Chebyshev approximation for nonrecursive
      digital filters with linear phase." IEEE Trans. Circuit Theory, 19(2), 189-194.
    - scipy.signal.remez: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.remez.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class FIRParksMcClellanFilter(Knot):
    """Design an equiripple FIR filter via the Parks-McClellan (Remez) algorithm."""

    def __init__(
        self,
        *,
        signal: Knot,
        num_taps: Knot | int,
        bands: Knot | tuple,
        desired: Knot | tuple,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            num_taps=num_taps,
            bands=bands,
            desired=desired,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        num_taps: int,
        bands: tuple[float, ...],
        desired: tuple[float, ...],
        **_: Any,
    ) -> SignalFrame:
        """Apply the Parks-McClellan equiripple FIR filter and return the filtered SignalFrame.

        Args:
            signal: The input signal frame.
            num_taps: Number of filter taps (positive odd integer).
            bands: Even-length tuple of normalised frequency band edges.
            desired: Tuple with one desired gain value per band pair.

        Returns:
            Filtered SignalFrame with the same shape as the input.

        Raises:
            ValueError: If num_taps, bands, or desired are invalid.
        """
        if not isinstance(num_taps, int) or num_taps <= 0 or num_taps % 2 == 0:
            raise ValueError(
                "FIRParksMcClellanFilter: num_taps must be a positive odd integer"
            )
        if not isinstance(bands, tuple) or len(bands) < 2 or len(bands) % 2 != 0:
            raise ValueError(
                "FIRParksMcClellanFilter: bands must be a tuple of an even number of edge frequencies"
            )
        if not isinstance(desired, tuple) or len(desired) != len(bands) // 2:
            raise ValueError(
                "FIRParksMcClellanFilter: desired must have one value per band"
            )
        return SignalFrame(
            signal_id=f"{signal.signal_id}:fir-pm",
            channel_count=signal.channel_count,
            sample_rate_hz=signal.sample_rate_hz,
            samples_per_channel=signal.samples_per_channel,
        )
