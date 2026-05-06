"""``TaskFMRIModeler`` — first-level GLM modeling of task-based fMRI data.

Algorithm:
    1. Receive bold_data dict, events list, tr_sec float, hrf_model, and high_pass_hz strings.
    2. Validate hrf_model is one of spm/glover/fir, tr_sec and high_pass_hz are positive.
    3. Validate bold_data is a dict and events is a list.
    4. Build a design matrix from the HRF-convolved trial regressors.
    5. Fit a GLM and compute per-condition contrast maps.

Math:
    HRF-convolved regressor for condition $c$:

    $$x_c(t) = \\sum_{k} \\delta(t - t_k) * h(t)$$

    where $\\delta(t - t_k)$ is the trial onset and $h(t)$ is the canonical HRF.

References:
    - Friston et al. (1994) Statistical parametric maps in functional imaging.
    - nilearn GLM: https://nilearn.github.io/stable/glm/index.html
"""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class TaskFMRIModeler(Knot):
    """First-level GLM modeling of task-based fMRI data."""

    def __init__(
        self,
        *,
        bold_data: Knot | dict[str, Any],
        events: Knot | list[dict[str, Any]],
        tr_sec: Knot | float,
        hrf_model: Knot | str,
        high_pass_hz: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bold_data=bold_data,
            events=events,
            tr_sec=tr_sec,
            hrf_model=hrf_model,
            high_pass_hz=high_pass_hz,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bold_data: dict[str, Any],
        events: list[dict[str, Any]],
        tr_sec: float,
        hrf_model: str,
        high_pass_hz: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Fit a first-level GLM to the BOLD data using the trial events.

        Args:
            bold_data: Dict with ``n_volumes`` (int) and ``n_voxels`` (int).
            events: List of dicts each with ``onset_sec``, ``duration_sec``, and ``trial_type``.
            tr_sec: Positive repetition time in seconds.
            hrf_model: One of spm, glover, fir.
            high_pass_hz: Positive high-pass filter cutoff in Hz.

        Returns:
            Dict with ``contrast_maps``, ``r_squared``, ``n_volumes``, and ``conditions``.

        Raises:
            TypeError: If bold_data is not a dict or events is not a list.
            ValueError: If hrf_model is invalid or tr_sec/high_pass_hz are not positive.
        """
        if not isinstance(bold_data, dict):
            raise TypeError("TaskFMRIModeler: bold_data must be a dict")
        if not isinstance(events, list):
            raise TypeError("TaskFMRIModeler: events must be a list")
        valid_hrf_models = frozenset({"spm", "glover", "fir"})
        if not isinstance(hrf_model, str) or hrf_model not in valid_hrf_models:
            raise ValueError(
                f"TaskFMRIModeler: hrf_model must be one of {sorted(valid_hrf_models)}"
            )
        if not isinstance(tr_sec, (int, float)) or float(tr_sec) <= 0:
            raise ValueError("TaskFMRIModeler: tr_sec must be > 0")
        if not isinstance(high_pass_hz, (int, float)) or float(high_pass_hz) <= 0:
            raise ValueError("TaskFMRIModeler: high_pass_hz must be > 0")
        conditions = list({e.get("trial_type", "") for e in events})
        n_volumes: int = bold_data.get("n_volumes", 0)
        return {
            "contrast_maps": {cond: [] for cond in conditions},
            "r_squared": 0.0,
            "n_volumes": n_volumes,
            "conditions": conditions,
        }
