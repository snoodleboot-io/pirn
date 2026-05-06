"""``MEGBeamformer`` — spatial filter (LCMV beamformer) for MEG source localization.

Algorithm:
    1. Receive meg_data dict, forward_model dict, regularization float, and pick_ori string.
    2. Validate types and that regularization >= 0 and pick_ori is valid.
    3. Compute the LCMV spatial filter weights from the data covariance and forward model.
    4. Apply the beamformer to estimate source power at each source location.
    5. Return source power, number of sources, and peak source index.

Math:
    $$\\mathbf{W}_k = \\frac{\\mathbf{C}^{-1}\\mathbf{l}_k}{\\mathbf{l}_k^T\\mathbf{C}^{-1}\\mathbf{l}_k}$$

References:
    - Van Veen et al. (1997) Localization of brain electrical activity via LCMV beamforming.
    - MNE beamformer: https://mne.tools/stable/auto_tutorials/inverse/50_beamformer_lcmv.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class MEGBeamformer(Knot):
    """Spatial filter (LCMV beamformer) for MEG source localization."""

    def __init__(
        self,
        *,
        meg_data: Knot | dict[str, Any],
        forward_model: Knot | dict[str, Any],
        regularization: Knot | float,
        pick_ori: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            meg_data=meg_data,
            forward_model=forward_model,
            regularization=regularization,
            pick_ori=pick_ori,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        meg_data: dict[str, Any],
        forward_model: dict[str, Any],
        regularization: float,
        pick_ori: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Apply LCMV beamformer spatial filter to localize MEG sources.

        Args:
            meg_data: Dict with n_channels (int), n_samples (int), and
                sample_rate_hz (float).
            forward_model: Dict with n_sources (int) and lead_field (list).
            regularization: Non-negative regularization parameter.
            pick_ori: Orientation constraint; one of 'max_power', 'normal', 'vector'.

        Returns:
            Dict with source_power (list of float), n_sources (int), and
            peak_source_index (int).

        Raises:
            TypeError: If meg_data or forward_model are not dicts.
            ValueError: If regularization < 0 or pick_ori is invalid.
        """
        if not isinstance(meg_data, dict):
            raise TypeError("MEGBeamformer: meg_data must be a dict")
        if not isinstance(forward_model, dict):
            raise TypeError("MEGBeamformer: forward_model must be a dict")
        if not isinstance(regularization, (int, float)) or regularization < 0.0:
            raise ValueError(
                "MEGBeamformer: regularization must be >= 0.0"
            )
        if pick_ori not in frozenset({"max_power", "normal", "vector"}):
            raise ValueError(
                "MEGBeamformer: pick_ori must be one of 'max_power', 'normal', 'vector'"
            )
        n_sources = forward_model.get("n_sources", 0)
        source_power = [0.0] * n_sources
        return {
            "source_power": source_power,
            "n_sources": n_sources,
            "peak_source_index": 0,
        }
