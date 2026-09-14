"""``PolyResampling`` — shared polyphase resampling helper (private, not a Knot).

Factors out the ``scipy.signal.resample_poly`` call that was duplicated
byte-for-byte across four resampling knots (:class:`ArbitraryResamplerPipeline`,
:class:`ClockDriftCorrector`, :class:`PolyphaseResampler`, and
:class:`RationalResamplerPipeline`). Each knot calls
:meth:`PolyResampling.resample_poly` from its own ``process()`` via
``asyncio.to_thread``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from pirn_signal.bindings.scipy_signal_binding import ScipySignalBinding


class PolyResampling:
    """Polyphase resampling shared by ``pirn_signal.resampling`` knots."""

    @staticmethod
    def resample_poly(
        data: NDArray[np.floating[Any]], up: int, down: int
    ) -> NDArray[np.floating[Any]]:
        ss = ScipySignalBinding.load()
        return ss.resample_poly(data, up, down, axis=-1)
