"""``run_eval`` — run a pattern/pipeline over an eval dataset and report quality.

Runs the evaluation on the engine: one
:class:`~pirn_agents.evaluation._eval_case._EvalCase` knot per
:class:`~pirn_agents.evaluation.eval_dataset.EvalDataset` item (target call,
metric scoring, threshold check) fanned into an
:class:`~pirn.nodes.aggregator.Aggregator` that assembles the
:class:`~pirn_agents.evaluation.eval_report.EvalReport` in dataset order.
In-flight items are bounded by ``KnotConfig(concurrency_group=...)`` on every
item knot and a ``ConcurrencyLimits`` group cap sized from ``concurrency`` —
the admission gate's own budget, so an eval started inside another run shares
that run's caps too (PIR-872; previously a bare ``asyncio.Semaphore`` and
``asyncio.gather``).

Determinism is core record/replay, not a separate cassette seam. Every eval run
records one lineage row and one content-addressed output per item into the
``history`` and ``data_store`` it runs against; passing ``replay=`` a
:class:`~pirn.recording.replay_session.ReplaySession` over a recorded eval run
serves each item's recorded result instead of calling the target, so a suite
records once and replays offline. Name the run with ``run_id=`` to find it again
(``ReplaySession.from_history(history=..., run_id=...)``); use a durable
``history``/``data_store`` to replay in another process. A replay whose dataset
items, target, metrics or thresholds differ from the recording raises
``ReplayMismatchError`` rather than serving a stale result (see
:class:`~pirn_agents.evaluation._eval_subject._EvalSubject` for how callables
are identified).

Algorithm:
    1. Validate the dataset, metrics and concurrency.
    2. An empty dataset returns an empty report.
    3. Build a tapestry over ``history``/``data_store``: one ``_EvalCase`` per
       item (``KnotConfig(id="eval_item_<index>",
       concurrency_group="eval_items")``) sharing one ``_EvalSubject``, joined
       by an ``Aggregator`` that orders the results by index.
    4. Run it with ``ConcurrencyLimits(groups={"eval_items": concurrency})``,
       live or under ``replay``.
    5. Raise ``EvalRunError`` when any item failed; otherwise return the
       aggregated report.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, ClassVar

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.evaluation._eval_case import _EvalCase
from pirn_agents.evaluation._eval_subject import _EvalSubject
from pirn_agents.evaluation.eval_case_result import EvalCaseResult
from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.eval_report import EvalReport
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.threshold_config import ThresholdConfig
from pirn_agents.exceptions.eval_run_error import EvalRunError

Target = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
EvalMetric = Callable[[EvalItem, Mapping[str, Any]], "MetricResult | Awaitable[MetricResult]"]


class RunEval:
    """Namespace for running a target over an eval dataset and scoring it."""

    #: The concurrency group every item knot joins; ``concurrency`` caps it.
    _item_group: ClassVar[str] = "eval_items"

    @staticmethod
    async def run(
        *,
        dataset: EvalDataset,
        target: Target,
        metrics: Mapping[str, EvalMetric],
        thresholds: ThresholdConfig | None = None,
        concurrency: int = 8,
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
        replay: ReplaySession | None = None,
        run_id: str | None = None,
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
            concurrency: Maximum number of simultaneously in-flight items; must
                be >= 1. Defaults to 8.
            history: The ``RunHistory`` the eval run records to (and a replay
                is loaded from); a fresh in-memory history when omitted.
            data_store: The ``DataStore`` item results are content-addressed
                into (and served from on replay); a fresh in-memory store when
                omitted.
            replay: A session over a recorded eval run to serve every item from
                instead of calling the target.
            run_id: The run id to record this eval under; generated when omitted.

        Replay identity:
            A replay is served only when the recording describes this exact
            evaluation: the same items, thresholds and metric names, and the
            same *code* for ``target`` and every metric. A Python function,
            lambda, bound method, ``functools.partial`` or object with a Python
            ``__call__`` is identified by its bytecode, constants (nested code
            objects included), names, defaults, closure cell values and bound
            arguments/object, so editing its body raises
            ``ReplayMismatchError``. **Fallback:** a callable with no
            inspectable code — a C builtin or extension callable — is
            identified by its ``module.qualname`` alone, so a change inside it
            is not detected and a replay can serve results recorded before
            that change. Likewise, a closure value or bound argument with no
            canonical content form is compared only by its type.

        Returns:
            An :class:`EvalReport` with one :class:`EvalCaseResult` per item, in
            dataset order.

        Raises:
            TypeError: If ``dataset`` is not an :class:`EvalDataset` or ``metrics``
                is not a mapping.
            ValueError: If ``concurrency`` is less than 1.
            EvalRunError: If any item's target call, metric or threshold check
                raised.
            ReplayMismatchError: If ``replay`` does not describe this evaluation.
        """
        if not isinstance(dataset, EvalDataset):
            raise TypeError(
                f"run_eval: dataset must be an EvalDataset, got {type(dataset).__name__}"
            )
        if not isinstance(metrics, Mapping):
            raise TypeError(f"run_eval: metrics must be a mapping, got {type(metrics).__name__}")
        if concurrency < 1:
            raise ValueError(f"run_eval: concurrency must be >= 1, got {concurrency}")
        if not dataset.items:
            return EvalReport()
        subject = _EvalSubject(target=target, metrics=dict(metrics), thresholds=thresholds)
        with Tapestry(history=history, data_store=data_store) as tapestry:
            cases: dict[str, Knot] = {
                f"case_{index}": _EvalCase(
                    item=item,
                    subject=subject,
                    _config=KnotConfig(
                        id=f"eval_item_{index}", concurrency_group=RunEval._item_group
                    ),
                )
                for index, item in enumerate(dataset.items)
            }
            report = Aggregator(
                combine=RunEval._report, _config=KnotConfig(id="eval_report"), **cases
            )
        limits = ConcurrencyLimits(groups={RunEval._item_group: concurrency})
        request = (
            RunRequest(concurrency=limits)
            if run_id is None
            else RunRequest(run_id=run_id, concurrency=limits)
        )
        run = await tapestry.run(request, terminals=report, replay=replay)
        if run.exceptions:
            raise EvalRunError(run)
        return run.outputs["eval_report"]

    @staticmethod
    def _report(**cases: EvalCaseResult) -> EvalReport:
        """Assemble the per-item results into a report, in dataset order."""
        return EvalReport(results=tuple(cases[f"case_{index}"] for index in range(len(cases))))
