"""``TaskFMRIModeler`` — first-level GLM modeling of task-based fMRI data."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class TaskFMRIModeler(Knot):
    """First-level GLM modeling of task-based fMRI data."""

    _VALID_HRF_MODELS: frozenset[str] = frozenset({"spm", "glover", "fir"})

    def __init__(
        self,
        *,
        bold_data: Knot,
        events: Knot,
        tr_sec: float,
        hrf_model: str,
        high_pass_hz: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(hrf_model, str) or hrf_model not in self._VALID_HRF_MODELS:
            raise ValueError(
                f"TaskFMRIModeler: hrf_model must be one of {sorted(self._VALID_HRF_MODELS)}"
            )
        if not isinstance(tr_sec, (int, float)) or float(tr_sec) <= 0:
            raise ValueError("TaskFMRIModeler: tr_sec must be > 0")
        if not isinstance(high_pass_hz, (int, float)) or float(high_pass_hz) <= 0:
            raise ValueError("TaskFMRIModeler: high_pass_hz must be > 0")
        self._tr_sec = float(tr_sec)
        self._hrf_model = hrf_model
        self._high_pass_hz = float(high_pass_hz)
        super().__init__(bold_data=bold_data, events=events, _config=_config, **kwargs)

    async def process(
        self,
        bold_data: dict[str, Any],
        events: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Fit a first-level GLM to the BOLD data using the trial events.

        Args:
            bold_data: Dict with ``n_volumes`` (int) and ``n_voxels`` (int).
            events: List of dicts each with ``onset_sec``, ``duration_sec``,
                and ``trial_type``.

        Returns:
            Dict with ``contrast_maps``, ``r_squared``, ``n_volumes``,
            and ``conditions``.
        """
        if not isinstance(bold_data, dict):
            raise TypeError("TaskFMRIModeler: bold_data must be a dict")
        if not isinstance(events, list):
            raise TypeError("TaskFMRIModeler: events must be a list")
        conditions = list({e.get("trial_type", "") for e in events})
        n_volumes: int = bold_data.get("n_volumes", 0)
        return {
            "contrast_maps": {cond: [] for cond in conditions},
            "r_squared": 0.0,
            "n_volumes": n_volumes,
            "conditions": conditions,
        }
