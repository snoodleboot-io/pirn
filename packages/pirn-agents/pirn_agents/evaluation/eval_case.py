"""``EvalCase`` — evaluate one dataset item: call the target, score it, check its floors.

Internal per-item knot of :meth:`~pirn_agents.evaluation.run_eval.RunEval.run`.
One ``EvalCase`` per :class:`~pirn_agents.evaluation.eval_item.EvalItem` runs
under the engine, so each item has its own lineage row, ``Result``, admission
slot (``KnotConfig(concurrency_group=...)`` bounded by ``ConcurrencyLimits``)
and recorded output — which is what makes a recorded eval replayable: served
from the recording, the target is never called again.

Algorithm:
    1. Await ``subject.target(item.input)`` for the produced output mapping.
    2. For each metric, call its scorer with ``(item, output)``, awaiting the
       result when the scorer is async, and keep its ``score``.
    3. Apply ``subject.thresholds``: when no metric has a floor the verdict is
       ``None``; otherwise the item passes iff every floored metric meets its
       floor, and each breach is recorded.
    4. Return an :class:`~pirn_agents.evaluation.eval_case_result.EvalCaseResult`
       whose ``detail`` carries the output and any breaches.

Math:
    For the metrics :math:`M_f \\subseteq M` that have a floor :math:`f_m`:

    $$
    \\text{passed} = \\begin{cases}
        \\text{None} & M_f = \\emptyset \\\\
        \\bigwedge_{m \\in M_f} \\left(s_m \\geq f_m\\right) & \\text{otherwise}
    \\end{cases}
    $$

Package-internal: constructed only by :meth:`~pirn_agents.evaluation.run_eval.RunEval.run`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.evaluation.eval_case_result import EvalCaseResult
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.eval_subject import EvalSubject
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.threshold_config import ThresholdConfig


class EvalCase(Knot):
    """Run the target on one item, score it, and apply the thresholds."""

    def __init__(
        self,
        *,
        item: EvalItem,
        subject: EvalSubject,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(item=item, subject=subject, _config=_config, **kwargs)

    async def process(self, item: EvalItem, subject: EvalSubject, **_: Any) -> EvalCaseResult:
        """Evaluate ``item`` against ``subject``.

        Args:
            item: The dataset item.
            subject: The target, metrics and thresholds under evaluation.

        Returns:
            The item's scores, verdict and detail.
        """
        output = await subject.target(item.input)
        scores: dict[str, float] = {}
        for name, scorer in subject.metrics.items():
            produced = scorer(item, output)
            metric_result = produced if isinstance(produced, MetricResult) else await produced
            scores[name] = metric_result.score
        passed, breaches = EvalCase._apply_thresholds(scores, subject.thresholds)
        detail: dict[str, Any] = {"output": dict(output)}
        if breaches:
            detail["breaches"] = breaches
        return EvalCaseResult(item_id=item.item_id, metrics=scores, passed=passed, detail=detail)

    @staticmethod
    def _apply_thresholds(
        scores: Mapping[str, float], thresholds: ThresholdConfig | None
    ) -> tuple[bool | None, list[dict[str, Any]]]:
        """Return ``(passed, breaches)`` for one item's ``scores``.

        ``passed`` is ``None`` when no threshold applies to any of the item's
        metrics; otherwise it is ``False`` iff any applicable metric fell below
        its floor. Each breach records the metric, its score, and the required
        minimum.
        """
        if thresholds is None:
            return None, []
        breaches: list[dict[str, Any]] = []
        applied = False
        for name, score in scores.items():
            minimum = thresholds.min_for(name)
            if minimum is None:
                continue
            applied = True
            if score < minimum:
                breaches.append({"metric": name, "score": score, "min_score": minimum})
        if not applied:
            return None, []
        return (len(breaches) == 0), breaches
