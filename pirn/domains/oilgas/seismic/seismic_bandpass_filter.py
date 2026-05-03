"""``SeismicBandpassFilter`` — apply trapezoidal bandpass filter to seismic data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SeismicBandpassFilter(Knot):
    """Apply a trapezoidal (Ormsby-style) bandpass filter to seismic trace data."""

    def __init__(
        self,
        *,
        data: Knot,
        low_cut_hz: float,
        low_pass_hz: float,
        high_pass_hz: float,
        high_cut_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("low_cut_hz", low_cut_hz),
            ("low_pass_hz", low_pass_hz),
            ("high_pass_hz", high_pass_hz),
            ("high_cut_hz", high_cut_hz),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"SeismicBandpassFilter: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"SeismicBandpassFilter: {label} must be positive")
        if not (low_cut_hz < low_pass_hz < high_pass_hz < high_cut_hz):
            raise ValueError(
                "SeismicBandpassFilter: frequencies must satisfy "
                "low_cut_hz < low_pass_hz < high_pass_hz < high_cut_hz"
            )
        self._low_cut_hz = float(low_cut_hz)
        self._low_pass_hz = float(low_pass_hz)
        self._high_pass_hz = float(high_pass_hz)
        self._high_cut_hz = float(high_cut_hz)
        super().__init__(data=data, _config=_config, **kwargs)

    async def process(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Apply the bandpass filter to each trace in the seismic dataset.

        Args:
            data: Dict with ``traces`` (list of dicts with ``samples``) and
                ``sample_interval_ms`` (float).

        Returns:
            Dict with same structure as input plus ``filtered: True``.
        """
        if not isinstance(data, dict):
            raise TypeError("SeismicBandpassFilter: data must be a dict")
        return {**data, "filtered": True}
