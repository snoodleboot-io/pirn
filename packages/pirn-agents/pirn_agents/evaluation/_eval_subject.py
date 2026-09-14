"""``_EvalSubject`` — what an eval run evaluates: the target, its metrics, its floors.

Internal value object for :meth:`~pirn_agents.evaluation.run_eval.RunEval.run`.
Every per-item knot of an eval run carries the same subject as a literal
constructor argument, so it is part of each item's recorded invocation identity
(``KnotLineage.config_values_hash``) and a replay refuses to serve a recording
made for a different subject.

Callables have no content, so a subject names each callable by its qualified
name (``module.qualname``, the type's for a callable instance) — stable across
processes, which is what lets a recorded eval replay in a fresh interpreter.
Renaming the target or a metric, adding or dropping a metric, or changing a
threshold makes a replay raise ``ReplayMismatchError``; editing a callable's body
under the same name does not, exactly as a knot's recorded row does not track
its ``process()`` body.

Internal API.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.threshold_config import ThresholdConfig


@dataclass(frozen=True)
class _EvalSubject(PirnOpaqueValue):
    """The target under evaluation, its metrics, and their optional floors.

    Attributes
    ----------
    target:
        Async callable mapping an item's ``input`` to a produced output mapping.
    metrics:
        Metric name to a scorer taking ``(item, output)`` and returning a
        :class:`~pirn_agents.evaluation.metric_result.MetricResult`, sync or
        awaitable.
    thresholds:
        Per-metric floors, or ``None``.
    """

    target: Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
    metrics: Mapping[str, Callable[[EvalItem, Mapping[str, Any]], Any]]
    thresholds: ThresholdConfig | None = None

    @staticmethod
    def _callable_name(candidate: object) -> str:
        """``module.qualname`` of a function, or of a callable instance's type."""
        module = getattr(candidate, "__module__", None)
        qualname = getattr(candidate, "__qualname__", None)
        if not isinstance(module, str) or not isinstance(qualname, str):
            module = type(candidate).__module__
            qualname = type(candidate).__qualname__
        return f"{module}.{qualname}"

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {
            "target": _EvalSubject._callable_name(self.target),
            "metrics": {
                name: _EvalSubject._callable_name(scorer)
                for name, scorer in sorted(self.metrics.items())
            },
            "thresholds": (None if self.thresholds is None else self.thresholds._pirn_audit_dict()),
        }

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.__pirn_canonical__()
