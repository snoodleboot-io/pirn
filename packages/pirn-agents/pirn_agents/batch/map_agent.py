"""``MapAgent`` — map an agent over a dataset through core's own scheduler.

ADR agents-speaks-core, WS4b. Where the pre-migration ``MapAgent`` was a
private ``asyncio.wait`` loop over a bare coroutine — its own admission
counter, its own retry loop, its own checkpoint store — this ``MapAgent`` is
a :class:`~pirn.nodes.sub_tapestry.SubTapestry` whose inner graph is one
:class:`~pirn_agents.batch._map_item._MapItem` knot per input item, joined by
a core :class:`~pirn.nodes.aggregator.Aggregator`:

* **Per-item isolation** is ``KnotConfig(error_policy=RECEIVE_ERRORS)`` on the
  aggregator: each item's ``Ok``/``Err``/``Skipped`` reaches the combine step
  as a value, so one item's failure never skips or poisons its siblings —
  the engine's own dependency-skip default (``SKIP_IF_PARENT_FAILED``) is what
  this policy turns off.
* **Bounded concurrency** is ``KnotConfig(concurrency_group=...)`` on every
  item plus a ``ConcurrencyLimits`` group cap on the run — the same
  ``Admission``/``ReadyQueue`` every other knot in the framework is
  scheduled through, not a private semaphore.
* **Per-item timeout/retry** is ``KnotConfig.timeout`` / ``KnotConfig.retry``
  (a ``KnotRetryPolicy``) on each item's knot — ``GovernedDispatch``'s job,
  not a hand-rolled ``run_with_retries``.
* **Resume-after-crash** is a ``RunHistory`` lineage query: an item's knot id
  is ``item:<batch_id>:<key>``, stable across runs, so a re-run with the same
  ``history=`` skips any item whose id already has an ``Ok`` lineage row. No
  checkpoint store is written or read.
* **Dispatcher choice** (Local/Thread/Ray/Dask), the **group cap** and
  **adaptive admission feedback** reach the inner run through core's own
  per-container overrides — ``SubTapestry._inner_dispatcher`` /
  ``_inner_concurrency`` / ``_inner_admission_observers`` (ADR WS0b) — and an
  unset dispatcher inherits the enclosing run's execution plane, like every
  other ``SubTapestry``.

Two ways to use it, matching the two things a ``Knot`` can be:

1. **Wired into a bigger pipeline** — pass ``items=`` a parent ``Knot`` (or a
   literal list) at construction; the engine calls this knot like any other,
   and its single output is the ``list[BatchItemResult]`` the aggregator
   combined.
2. **Standalone** — :meth:`run` is the one-cycle deprecation shim preserving
   the pre-migration ``async for result in map_agent.run(inputs)`` contract:
   it builds a throwaway ``Tapestry``, runs the same item/aggregator graph,
   and yields each ``BatchItemResult`` **the instant its item settles**,
   before the join completes — an
   :class:`~pirn_agents.batch._batch_item_streamer._BatchItemStreamer`
   emitter turns core's ``Emitter.on_knot_result`` (ADR WS0b) into the
   stream, so the ``Err``'s full ``ExceptionRecord``, the attempt count and
   the latency ride along from the lineage row.

   Trade-off, disclosed: ``inputs`` is still materialised up front — the
   resume lookup and the item graph need every key before the run starts —
   so the pre-migration lazy pull of the input iterable does not apply.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.batch._batch_item_streamer import _BatchItemStreamer
from pirn_agents.batch._map_item import _MapItem
from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController
from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.resilience.token_bucket_rate_limiter import TokenBucketRateLimiter

if TYPE_CHECKING:
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.result import Result
    from pirn.engine.admission.admission_observer import AdmissionObserver
    from pirn.engine.dispatchers.dispatcher import Dispatcher


class MapAgent(SubTapestry):
    """Map a per-item agent over a batch, scheduled entirely by the core engine."""

    def __init__(
        self,
        run_item: Callable[[object], Awaitable[object]],
        *,
        batch_id: str = "batch",
        concurrency: int = 8,
        concurrency_group: str = "map_agent_items",
        timeout: float | None = None,
        retries: int = 0,
        retry: KnotRetryPolicy | None = None,
        key_fn: Callable[[object], str] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        concurrency_controller: AdaptiveConcurrencyController | None = None,
        dispatcher: Dispatcher | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
        items: Any = None,
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        """Build the batch runner.

        Args:
            run_item: The per-item agent callable — ``async (item) -> output``.
            batch_id: Stable id naming this batch. Namespaces every item's
                knot id (``item:<batch_id>:<key>``), which is both its
                admission/lineage identity and its resume key.
            concurrency: Maximum simultaneously in-flight items — the run's
                ``ConcurrencyLimits`` group cap. Must be >= 1. Ignored when
                ``concurrency_controller`` is set (its own limit wins).
            concurrency_group: The ``KnotConfig.concurrency_group`` every
                item is admitted under. Give ``MapAgent`` instances that run
                concurrently and must not share a budget distinct groups.
            timeout: Per-item ``KnotConfig.timeout`` in seconds, or ``None``
                to disable. Bounds one attempt, not the retry budget.
            retries: Extra attempts granted to an item that raises. Must be
                >= 0. Builds a default ``KnotRetryPolicy(max_attempts=retries+1)``
                when ``retry`` is not given explicitly.
            retry: A ``KnotRetryPolicy`` overriding ``retries``' default
                policy — set this for backoff/jitter/``is_retryable`` control.
            key_fn: Maps an input item to a stable string key (for de-dup on
                resume and for the item's knot id). Defaults to the item's
                stream index.
            rate_limiter: An optional shared
                :class:`~pirn_agents.resilience.token_bucket_rate_limiter.TokenBucketRateLimiter`.
                When set, every attempt acquires one token before running.
            concurrency_controller: An optional
                :class:`~pirn_agents.batch.adaptive_concurrency_controller.AdaptiveConcurrencyController`.
                When set, it is bound to ``concurrency_group`` and its limit
                (not ``concurrency``) seeds the run's group cap; it then
                steers that cap live via the run's ``Admission``.
            dispatcher: The engine ``Dispatcher`` (Local/Thread/Ray/Dask) this
                batch's items run under. ``None`` inherits the ambient run's.
            admission_observers: Extra observers attached to the run
                alongside ``concurrency_controller`` (if set).
            history: A ``RunHistory`` to resume from. ``None`` disables
                resume — every item runs regardless of prior lineage.
            data_store: The value plane for a standalone :meth:`run`; ignored
                when this knot is engine-invoked (it inherits the enclosing
                run's data store like any ``SubTapestry``).
            items: The dataset, when wiring this knot into a bigger pipeline —
                a parent ``Knot`` or a literal list/tuple. Unused by the
                standalone :meth:`run` shim, which takes its inputs there.
            _config: Framework config. Defaults to
                ``KnotConfig(id=f"map-agent:{batch_id}")`` so standalone use
                needs no explicit id.
            tapestry: Explicit tapestry to register into; defaults to the
                ambient one, like any other knot.

        Raises:
            TypeError: If ``run_item`` is not callable, or ``rate_limiter`` /
                ``concurrency_controller`` are of the wrong type.
            ValueError: If ``concurrency`` < 1, ``retries`` < 0, or
                ``batch_id`` is empty.
        """
        if not callable(run_item):
            raise TypeError(f"MapAgent: run_item must be callable, got {type(run_item).__name__}")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("MapAgent: batch_id must be a non-empty str")
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
            raise ValueError(f"MapAgent: concurrency must be an int >= 1, got {concurrency!r}")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"MapAgent: retries must be an int >= 0, got {retries!r}")
        if rate_limiter is not None and not isinstance(rate_limiter, TokenBucketRateLimiter):
            raise TypeError(
                f"MapAgent: rate_limiter must be a TokenBucketRateLimiter or None, "
                f"got {type(rate_limiter).__name__}"
            )
        if concurrency_controller is not None and not isinstance(
            concurrency_controller, AdaptiveConcurrencyController
        ):
            raise TypeError(
                f"MapAgent: concurrency_controller must be an AdaptiveConcurrencyController "
                f"or None, got {type(concurrency_controller).__name__}"
            )

        resolved_config = _config if _config is not None else KnotConfig(id=f"map-agent:{batch_id}")
        super().__init__(items=items, _config=resolved_config, tapestry=tapestry)

        if concurrency_controller is not None:
            concurrency_controller.bind_to_group(concurrency_group)

        self._mutable_run_item = run_item
        self._mutable_batch_id = batch_id
        self._mutable_concurrency = concurrency
        self._mutable_concurrency_group = concurrency_group
        self._mutable_timeout = timeout
        self._mutable_retry = (
            retry if retry is not None else KnotRetryPolicy(max_attempts=retries + 1)
        )
        self._mutable_key_fn = key_fn
        self._mutable_rate_limiter = rate_limiter
        self._mutable_controller = concurrency_controller
        self._mutable_dispatcher = dispatcher
        self._mutable_admission_observers = list(admission_observers or [])
        self._mutable_history = history
        self._mutable_data_store = data_store
        self._mutable_live_items = 0

    # ------------------------------------------------ engine-invoked path

    async def process(self, items: Any = None, **_: Any) -> Knot:
        """Build the per-item + aggregator graph for this run.

        Args:
            items: The resolved dataset — whatever the constructor's
                ``items=`` (a parent knot's output, or the literal passed
                through) resolved to. Must be a list/tuple.

        Returns:
            The ``Aggregator`` (or, when every item already resumed, a tiny
            pass-through sink) whose output is ``list[BatchItemResult]``.
        """
        item_list = list(items) if items is not None else []
        history = (
            self._mutable_history
            if self._mutable_history is not None
            else self._mutable_outer_history
        )
        resumed = await self._resume_lookup(item_list, self._mutable_batch_id, history)
        # Read by ``_inner_concurrency`` once the graph is built: a group cap
        # with nothing left to run is left undeclared, since naming an unused
        # group only warns (``UnusedConcurrencyGroupWarning``) but is needless
        # noise for the common "everything already resumed" case.
        self._mutable_live_items = len(item_list) - len(resumed)
        return self._build_graph(item_list, self._mutable_batch_id, resumed)

    # ------------------------------------ inner-run overrides (core seams)

    def _inner_dispatcher(self) -> Dispatcher | None:
        """This batch's dispatcher; ``None`` inherits the enclosing run's (WS0b)."""
        return self._mutable_dispatcher

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """The group cap the items are admitted under, or ``None`` when nothing runs."""
        if self._mutable_live_items <= 0:
            return None
        return ConcurrencyLimits(
            groups={self._mutable_concurrency_group: self._effective_group_limit()}
        )

    def _inner_admission_observers(self) -> list[AdmissionObserver] | None:
        """The batch's observers (controller included); ``None`` when there are none."""
        observers = self._observers_for_run()
        return observers or None

    def _effective_group_limit(self) -> int:
        if self._mutable_controller is not None:
            return self._mutable_controller.limit()
        return self._mutable_concurrency

    def _observers_for_run(self) -> list[AdmissionObserver]:
        observers = list(self._mutable_admission_observers)
        if self._mutable_controller is not None:
            observers.append(self._mutable_controller)
        return observers

    # ------------------------------------------------------ standalone path

    async def run(
        self, inputs: Iterable[object], *, checkpoint_scope: str | None = None
    ) -> AsyncIterator[BatchItemResult]:
        """Run the agent over ``inputs``, yielding each item's result as it settles.

        One-cycle deprecation shim preserving the pre-migration streaming
        contract. Builds a throwaway ``Tapestry`` with a
        :class:`~pirn_agents.batch._batch_item_streamer._BatchItemStreamer`
        emitter attached, starts the item/aggregator graph as a task, and
        yields a ``BatchItemResult`` the moment core's
        ``Emitter.on_knot_result`` reports the item knot settled (ADR WS0b) —
        resumed items first, then live items in completion order. Closing the
        generator early (``break``, ``aclose``) or cancelling its consumer
        cancels the run, and with it every in-flight item.

        Args:
            inputs: The dataset to map over. Materialised eagerly (a
                behaviour change from the pre-migration lazy pull — see the
                module docstring).
            checkpoint_scope: Namespaces this run's resume key, mirroring the
                pre-migration ``BatchCheckpointer.scoped`` suffix: the
                effective batch id becomes ``f"{batch_id}:{checkpoint_scope}"``.
                ``None`` (the default) uses ``batch_id`` itself.

        Yields:
            One ``BatchItemResult`` per input item.

        Raises:
            TypeError: If ``checkpoint_scope`` is neither ``None`` nor a ``str``.
        """
        if checkpoint_scope is not None and not isinstance(checkpoint_scope, str):
            raise TypeError(
                f"MapAgent.run: checkpoint_scope must be a str or None, "
                f"got {type(checkpoint_scope).__name__}"
            )
        items = list(inputs)
        batch_id = (
            self._mutable_batch_id
            if checkpoint_scope is None
            else f"{self._mutable_batch_id}:{checkpoint_scope}"
        )
        history = self._mutable_history
        resumed = await self._resume_lookup(items, batch_id, history)
        for index in sorted(resumed):
            yield resumed[index]

        live: dict[str, tuple[int, str]] = {}
        for index, item in enumerate(items):
            if index not in resumed:
                key = self._key_for(index, item)
                live[MapAgent._item_knot_id(batch_id, key)] = (index, key)
        queue: asyncio.Queue[BatchItemResult | None] = asyncio.Queue()
        streamer = _BatchItemStreamer(items_by_knot_id=live, queue=queue)
        run_tapestry = Tapestry(
            history=history,
            data_store=self._mutable_data_store,
            dispatcher=self._mutable_dispatcher,
            emitters=[streamer],
        )
        run_concurrency = (
            ConcurrencyLimits(
                groups={self._mutable_concurrency_group: self._effective_group_limit()}
            )
            if live
            else None
        )
        with run_tapestry:
            self._build_graph(items, batch_id, resumed)
        # One task: the engine run itself, so the stream below can be drained
        # while the engine schedules the items.  Every item is still admitted,
        # dispatched, timed out and retried by the engine, not here.
        run_task = asyncio.create_task(
            run_tapestry.run(
                RunRequest(concurrency=run_concurrency),
                admission_observers=self._observers_for_run(),
            )
        )
        run_task.add_done_callback(MapAgent._signal_run_over(queue))
        try:
            while True:
                settled = await queue.get()
                if settled is None:
                    break
                yield settled
        except BaseException:
            # The consumer stopped (cancelled, or closed the generator): stop
            # the run too, and wait for its in-flight items to wind down so
            # nothing keeps running behind a consumer that has gone away.
            run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await run_task
            await run_tapestry.close()
            raise
        # Surface a run-level failure (a refused group, a replay mismatch)
        # rather than ending the stream quietly short.
        await run_task
        await run_tapestry.close()

    @staticmethod
    def _signal_run_over(
        queue: asyncio.Queue[BatchItemResult | None],
    ) -> Callable[[asyncio.Future[Any]], None]:
        """Build the done-callback that ends the stream once the run task finishes."""

        # ``add_done_callback`` takes a one-argument callable and the queue
        # can only reach it by closure; the same shape as ``_make_combine``.
        # design-decision-override
        def signal(_: asyncio.Future[Any]) -> None:
            queue.put_nowait(None)

        return signal

    # ------------------------------------------------------------- shared

    def _key_for(self, index: int, item: object) -> str:
        if self._mutable_key_fn is None:
            return str(index)
        key = self._mutable_key_fn(item)
        if not isinstance(key, str) or not key:
            raise TypeError(f"MapAgent: key_fn must return a non-empty str, got {key!r}")
        return key

    async def _resume_lookup(
        self, items: list[Any], batch_id: str, history: RunHistory | None
    ) -> dict[int, BatchItemResult]:
        """Return ``{index: BatchItemResult(SKIPPED)}`` for items already ``Ok`` in *history*."""
        if history is None:
            return {}
        resumed: dict[int, BatchItemResult] = {}
        for index, item in enumerate(items):
            key = self._key_for(index, item)
            item_id = MapAgent._item_knot_id(batch_id, key)
            rows = await history.query_lineage_by_knot_id(item_id)
            if any(row.outcome == "ok" for row in rows):
                resumed[index] = BatchItemResult(
                    index=index, key=key, status=BatchItemStatus.SKIPPED
                )
        return resumed

    def _build_graph(
        self, items: list[Any], batch_id: str, resumed: dict[int, BatchItemResult]
    ) -> Knot:
        """Build the per-item knots and their joining ``Aggregator`` (or an all-resumed sink)."""
        on_throttle = (
            self._mutable_controller.on_throttle if self._mutable_controller is not None else None
        )
        order: list[tuple[str, int, str]] = []
        parents: dict[str, Knot] = {}
        for index, item in enumerate(items):
            if index in resumed:
                continue
            key = self._key_for(index, item)
            parent_key = f"p{index}"
            parents[parent_key] = _MapItem(
                item=item,
                run_item=self._mutable_run_item,
                rate_limiter=self._mutable_rate_limiter,
                on_throttle=on_throttle,
                _config=KnotConfig(
                    id=MapAgent._item_knot_id(batch_id, key),
                    concurrency_group=self._mutable_concurrency_group,
                    timeout=self._mutable_timeout,
                    retry=self._mutable_retry,
                ),
            )
            order.append((parent_key, index, key))
        combine = MapAgent._make_combine(len(items), order, resumed)
        if not parents:
            # Nothing left to run: the pre-computed result list re-enters the graph
            # as a plain core Parameter (the sanctioned shape for a constant sink).
            return Parameter(
                f"{batch_id}:aggregate",
                list,
                default=combine(),
                _config=KnotConfig(id=f"{batch_id}:aggregate"),
            )
        return Aggregator(
            combine=combine,
            _config=KnotConfig(id=f"{batch_id}:aggregate", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            **parents,
        )

    @staticmethod
    def _item_knot_id(batch_id: str, key: str) -> str:
        return f"item:{batch_id}:{key}"

    @staticmethod
    def _make_combine(
        total: int, order: list[tuple[str, int, str]], resumed: dict[int, BatchItemResult]
    ) -> Callable[..., list[BatchItemResult]]:
        """Build the ``RECEIVE_ERRORS`` combine turning each item's ``Result`` into a ``BatchItemResult``.

        Attempts and latency are not populated here (default to ``1`` /
        ``0.0``): a ``Result`` carries neither, only the run's
        ``KnotLineage`` does (``extra["attempts"]``, ``duration_ms``) — a
        disclosed trade-off of joining through a plain ``Aggregator``. A
        caller needing exact figures reads ``RunResult.lineage`` for the
        item's knot id instead.
        """

        # Aggregator's combine hook takes only the resolved **inputs kwargs,
        # so the per-item order/resumed lookup can only reach it by closing
        # over them in a factory-built callable (same shape as
        # ParallelSpecialistFanOut._make_mapping_combine).
        # design-decision-override
        def combine(**inputs: Result[Any]) -> list[BatchItemResult]:
            by_index: dict[int, BatchItemResult] = dict(resumed)
            for parent_key, index, key in order:
                by_index[index] = BatchItemResult.from_result(
                    index=index, key=key, result=inputs[parent_key]
                )
            return [by_index[i] for i in range(total)]

        return combine
