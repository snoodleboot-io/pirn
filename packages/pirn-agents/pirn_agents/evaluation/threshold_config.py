"""``ThresholdConfig`` — the set of per-metric thresholds a run must clear."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.metric_threshold import MetricThreshold


@dataclass(frozen=True)
class ThresholdConfig(PirnOpaqueValue):
    """A collection of :class:`MetricThreshold`\\ s keyed by metric name.

    The regression-gate configuration a CI job loads alongside an eval report:
    every configured metric must meet its floor for the build to pass. Serialises
    to/from JSON so it can live beside the report as a checked-in artifact.

    Attributes
    ----------
    thresholds:
        The per-metric minimum-score thresholds (metric names must be unique).
    """

    thresholds: tuple[MetricThreshold, ...] = ()

    def __post_init__(self) -> None:
        """Validate, normalise, and de-duplicate the thresholds.

        Raises:
            TypeError: If ``thresholds`` is not a sequence of
                :class:`MetricThreshold`.
            ValueError: If two thresholds target the same metric.
        """
        if isinstance(self.thresholds, (str, bytes)) or not isinstance(self.thresholds, Sequence):
            raise TypeError(
                f"ThresholdConfig.thresholds must be a sequence of MetricThreshold, "
                f"got {type(self.thresholds).__name__}"
            )
        thresholds = tuple(self.thresholds)
        seen: set[str] = set()
        for index, threshold in enumerate(thresholds):
            if not isinstance(threshold, MetricThreshold):
                raise TypeError(
                    f"ThresholdConfig.thresholds[{index}] must be a MetricThreshold, "
                    f"got {type(threshold).__name__}"
                )
            if threshold.metric in seen:
                raise ValueError(
                    f"ThresholdConfig: duplicate threshold for metric {threshold.metric!r}"
                )
            seen.add(threshold.metric)
        object.__setattr__(self, "thresholds", thresholds)

    def min_for(self, metric: str) -> float | None:
        """Return the configured minimum for ``metric``, or ``None`` if unset."""
        for threshold in self.thresholds:
            if threshold.metric == metric:
                return threshold.min_score
        return None

    @classmethod
    def from_json(cls, data: str) -> ThresholdConfig:
        """Reconstruct a config from its :meth:`to_json` form."""
        payload = json.loads(data)
        thresholds = tuple(
            MetricThreshold(metric=item["metric"], min_score=item["min_score"])
            for item in payload.get("thresholds", [])
        )
        return cls(thresholds=thresholds)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the config to a stable, machine-readable JSON string."""
        payload = {
            "thresholds": [{"metric": t.metric, "min_score": t.min_score} for t in self.thresholds]
        }
        return json.dumps(payload, indent=indent, sort_keys=True)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"thresholds": [t._pirn_audit_dict() for t in self.thresholds]}
