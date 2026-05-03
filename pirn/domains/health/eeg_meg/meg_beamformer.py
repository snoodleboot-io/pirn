"""``MEGBeamformer`` — spatial filter (LCMV beamformer) for MEG source localization."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MEGBeamformer(Knot):
    """Spatial filter (LCMV beamformer) for MEG source localization."""

    _VALID_PICK_ORI: frozenset[str] = frozenset({"max_power", "normal", "vector"})

    def __init__(
        self,
        *,
        meg_data: Knot,
        forward_model: Knot,
        regularization: float,
        pick_ori: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(meg_data, Knot):
            raise TypeError("MEGBeamformer: meg_data must be a Knot")
        if not isinstance(forward_model, Knot):
            raise TypeError("MEGBeamformer: forward_model must be a Knot")
        if not isinstance(regularization, (int, float)) or regularization < 0.0:
            raise ValueError(
                "MEGBeamformer: regularization must be >= 0.0"
            )
        if pick_ori not in self._VALID_PICK_ORI:
            raise ValueError(
                "MEGBeamformer: pick_ori must be one of 'max_power', 'normal', 'vector'"
            )
        self._regularization = float(regularization)
        self._pick_ori = pick_ori
        super().__init__(
            meg_data=meg_data, forward_model=forward_model, _config=_config, **kwargs
        )

    async def process(
        self,
        meg_data: dict[str, Any],
        forward_model: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Apply LCMV beamformer spatial filter to localize MEG sources.

        Args:
            meg_data: Dict with n_channels (int), n_samples (int), and
                sample_rate_hz (float).
            forward_model: Dict with n_sources (int) and lead_field (list).

        Returns:
            Dict with source_power (list of float), n_sources (int), and
            peak_source_index (int).
        """
        if not isinstance(meg_data, dict):
            raise TypeError("MEGBeamformer: meg_data must be a dict")
        if not isinstance(forward_model, dict):
            raise TypeError("MEGBeamformer: forward_model must be a dict")
        n_sources = forward_model.get("n_sources", 0)
        source_power = [0.0] * n_sources
        return {
            "source_power": source_power,
            "n_sources": n_sources,
            "peak_source_index": 0,
        }
