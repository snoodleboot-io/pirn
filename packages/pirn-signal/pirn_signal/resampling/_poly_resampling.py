"""``PolyResampling`` — shared polyphase resampling helper (private, not a Knot).

Factors out the ``scipy.signal.resample_poly`` call that was duplicated
byte-for-byte across four resampling knots (:class:`ArbitraryResamplerPipeline`,
:class:`ClockDriftCorrector`, :class:`PolyphaseResampler`, and
:class:`RationalResamplerPipeline`). Each knot calls
:meth:`PolyResampling.resample_poly` from its own ``process()`` via
``asyncio.to_thread``.
"""

from __future__ import annotations

import numpy as np


class PolyResampling:
    """Polyphase resampling shared by ``pirn_signal.resampling`` knots."""

    @staticmethod
    def resample_poly(data: np.ndarray, up: int, down: int) -> np.ndarray:
        try:
            from scipy import signal as ss  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "PolyResampling requires 'scipy'. Install via pip install pirn-signal[signal]"
            ) from exc
        return np.asarray(ss.resample_poly(data, up, down, axis=-1))
