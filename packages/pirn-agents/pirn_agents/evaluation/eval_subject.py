"""``EvalSubject`` — what an eval run evaluates: the target, its metrics, its floors.

Internal value object for :meth:`~pirn_agents.evaluation.run_eval.RunEval.run`.
Every per-item knot of an eval run carries the same subject as a literal
constructor argument, so it is part of each item's recorded invocation identity
(``KnotLineage.config_values_hash``) and a replay refuses to serve a recording
made for a different subject.

Callables have no value ``ContentHasher.hash`` can canonicalise, so a subject
identifies each one by its code through
:class:`~pirn_agents.evaluation.callable_identity.CallableIdentity`: the
bytecode, constants (nested code objects included), names, defaults, closure
cell values, a ``functools.partial``'s bound arguments and a bound method's
object. Editing a target's or metric's body, rebinding a partial, adding or
dropping a metric, or changing a threshold therefore makes a replay raise
``ReplayMismatchError``. Only a callable with no inspectable code (a C builtin)
is identified by ``module.qualname`` alone.

Package-internal: constructed only by :meth:`~pirn_agents.evaluation.run_eval.RunEval.run`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.callable_identity import CallableIdentity
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.threshold_config import ThresholdConfig


@dataclass(frozen=True)
class EvalSubject(PirnOpaqueValue):
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
    metrics: Mapping[
        str, Callable[[EvalItem, Mapping[str, Any]], MetricResult | Awaitable[MetricResult]]
    ]
    thresholds: ThresholdConfig | None = None

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {
            "target": CallableIdentity.of(self.target),
            "metrics": {
                name: CallableIdentity.of(scorer) for name, scorer in sorted(self.metrics.items())
            },
            "thresholds": None if self.thresholds is None else self._audit(self.thresholds),
        }

    @staticmethod
    def _audit(value: PirnOpaqueValue) -> dict[str, Any]:
        """Audit a child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.__pirn_canonical__()
