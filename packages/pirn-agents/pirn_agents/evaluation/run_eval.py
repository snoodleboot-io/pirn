"""``run_eval`` — run a pattern/pipeline over an eval dataset and report quality.

Executes each :class:`~pirn_agents.evaluation.eval_dataset.EvalDataset` item
concurrently through the shared bounded-concurrency limiter
(:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`,
the same F1/F10 executor posture), scores it with the supplied metrics, applies
threshold pass/fail, and collects an
:class:`~pirn_agents.evaluation.eval_report.EvalReport`.

Determinism is a documented seam: every target invocation is routed through a
:class:`~pirn_agents.evaluation.run_recorder.RunRecorder` (defaulting to the
live-I/O :class:`~pirn_agents.evaluation.null_run_recorder.NullRunRecorder`), so
F29's cassette recorder can make a full suite deterministic without touching this
runner.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pirn_agents.evaluation.eval_case_result import EvalCaseResult
from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.eval_report import EvalReport
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.null_run_recorder import NullRunRecorder
from pirn_agents.evaluation.run_recorder import RunRecorder
from pirn_agents.evaluation.threshold_config import ThresholdConfig
from pirn_agents.performance.backpressure_semaphore import BackpressureSemaphore
from pirn_agents.performance.concurrency_config import ConcurrencyConfig

Target = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
Metric = Callable[[EvalItem, Mapping[str, Any]], "MetricResult | Awaitable[MetricResult]"]


async def run_eval(
    *,
    dataset: EvalDataset,
    target: Target,
    metrics: Mapping[str, Metric],
    thresholds: ThresholdConfig | None = None,
    concurrency: ConcurrencyConfig | None = None,
    recorder: RunRecorder | None = None,
) -> EvalReport:
    """Evaluate ``target`` over ``dataset`` and return an :class:`EvalReport`.

    Args:
        dataset: The fixture dataset to run.
        target: Async callable mapping an item's ``input`` to a produced output
            mapping (the pattern/pipeline under test).
        metrics: Mapping of metric name to a scorer callable taking
            ``(item, output)`` and returning a :class:`MetricResult` (sync or
            awaitable).
        thresholds: Optional per-metric floors; when given, each item's ``passed``
            is set and any breach is recorded in its detail.
        concurrency: Bounded-concurrency posture; defaults to
            :class:`ConcurrencyConfig` (8-way).
        recorder: Record/replay seam for the target call; defaults to the live
            :class:`NullRunRecorder` (F29 supplies a cassette-backed recorder).

    Returns:
        An :class:`EvalReport` with one :class:`EvalCaseResult` per item, in
        dataset order.

    Raises:
        TypeError: If ``dataset`` is not an :class:`EvalDataset` or ``metrics``
            is not a mapping.
    """
    if not isinstance(dataset, EvalDataset):
        raise TypeError(f"run_eval: dataset must be an EvalDataset, got {type(dataset).__name__}")
    if not isinstance(metrics, Mapping):
        raise TypeError(f"run_eval: metrics must be a mapping, got {type(metrics).__name__}")
    limiter = BackpressureSemaphore(concurrency if concurrency is not None else ConcurrencyConfig())
    active_recorder = recorder if recorder is not None else NullRunRecorder()

    async def _run_item(item: EvalItem) -> EvalCaseResult:
        async with limiter.slot():
            output = await active_recorder.invoke(
                key=item.item_id, thunk=lambda: target(item.input)
            )
            scores: dict[str, float] = {}
            for name, scorer in metrics.items():
                produced = scorer(item, output)
                metric_result = await produced if inspect.isawaitable(produced) else produced
                scores[name] = metric_result.score
            passed, breaches = _apply_thresholds(scores, thresholds)
            detail: dict[str, Any] = {"output": dict(output)}
            if breaches:
                detail["breaches"] = breaches
            return EvalCaseResult(
                item_id=item.item_id, metrics=scores, passed=passed, detail=detail
            )

    results = await asyncio.gather(*(_run_item(item) for item in dataset.items))
    return EvalReport(results=tuple(results))


def _apply_thresholds(
    scores: Mapping[str, float], thresholds: ThresholdConfig | None
) -> tuple[bool | None, list[dict[str, Any]]]:
    """Return ``(passed, breaches)`` for one item's ``scores``.

    ``passed`` is ``None`` when no threshold applies to any of the item's
    metrics; otherwise it is ``False`` iff any applicable metric fell below its
    floor. Each breach records the metric, its score, and the required minimum.
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
