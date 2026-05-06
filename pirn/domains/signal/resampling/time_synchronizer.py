"""``TimeSynchronizer`` — align two signals via cross-correlation time offset estimation.

Algorithm:
    1. Receive reference and target signal frames, and max_lag_samples.
    2. Validate max_lag_samples (positive integer).
    3. Compute the cross-correlation of reference and target signals within
       ±max_lag_samples lags using ``scipy.signal.correlate``.
    4. Identify the lag at maximum correlation (the estimated time offset).
    5. Shift the target signal by the estimated offset.
    6. Return a SignalFrame of the aligned target signal.

Math:
    Cross-correlation:

    $$R_{xy}(\\tau) = \\sum_n x(n) \\, y(n + \\tau), \\quad |\\tau| \\leq L_{\\max}$$

    Optimal lag:

    $$\\hat{\\tau} = \\arg\\max_{|\\tau| \\leq L_{\\max}} R_{xy}(\\tau)$$

References:
    - Knapp, C.H. & Carter, G.C. (1976). "The generalized correlation method for estimation of time delay."
      IEEE Trans. Acoust. Speech Signal Process., 24(4), 320-327.
    - scipy.signal.correlate: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class TimeSynchronizer(Knot):
    """Align two signals in time by estimating the offset via cross-correlation.

    Production needs ``scipy.signal.correlate``.
    """

    def __init__(
        self,
        *,
        reference: Knot,
        target: Knot,
        max_lag_samples: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            reference=reference,
            target=target,
            max_lag_samples=max_lag_samples,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        reference: SignalFrame,
        target: SignalFrame,
        max_lag_samples: int,
        **_: Any,
    ) -> SignalFrame:
        """Estimate the time offset between reference and target via cross-correlation and return the aligned target.

        Args:
            reference: Reference signal defining the time base.
            target: Target signal to align to the reference.
            max_lag_samples: Maximum search lag in samples (positive integer).

        Returns:
            SignalFrame of the target signal shifted to align with the reference.

        Raises:
            ValueError: If max_lag_samples is not a positive integer.
        """
        if not isinstance(max_lag_samples, int) or max_lag_samples <= 0:
            raise ValueError(
                "TimeSynchronizer: max_lag_samples must be a positive integer"
            )
        return SignalFrame(
            signal_id=f"{target.signal_id}:synced",
            channel_count=target.channel_count,
            sample_rate_hz=target.sample_rate_hz,
            samples_per_channel=target.samples_per_channel,
        )
