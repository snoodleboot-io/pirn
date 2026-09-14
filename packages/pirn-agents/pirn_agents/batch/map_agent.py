"""``MapAgent`` — map an agent over a dataset through core's own scheduler.

ADR agents-speaks-core, WS4b. ``MapAgent`` is a
:class:`~pirn.nodes.sub_tapestry.SubTapestry` whose inner graph is one
:class:`~pirn_agents.batch._map_item._MapItem` knot per input item, joined by
a core :class:`~pirn.nodes.aggregator.Aggregator`:

* **Per-item isolation** is ``KnotConfig(error_policy=RECEIVE_ERRORS)`` on the
  aggregator: each item's ``Ok``/``Err``/``Skipped`` reaches the combine step
  as a value, so one item's failure never skips or poisons its siblings —
  the engine's own dependency-skip default (``SKIP_IF_PARENT_FAILED``) is what
  this policy turns off.
* **Bounded concurrency** is ``KnotConfig(concurrency_group=...)`` on every
  item plus a ``ConcurrencyLimits`` group cap on the run — the same
  ``AdmissionGate``/``ReadyQueue`` every other knot in the framework is
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

Every setting is a declared knot input (knot-design-rules.md Rules 1-4): the
constructor only wires them, and ``process()`` validates them and builds the
graph. Two ways to use it, matching the two things a ``Knot`` can be:

1. **Wired into a bigger pipeline** — pass ``items=`` a parent ``Knot`` (or a
   literal list) at construction; the engine calls this knot like any other,
   and its single output is the ``list[BatchItemResult]`` the aggregator
   combined.
2. **Standalone streaming** — :meth:`run` builds a throwaway ``Tapestry``,
   runs the same item/aggregator graph, and yields each ``BatchItemResult``
   **the instant its item settles**, before the join completes — an
   :class:`~pirn_agents.batch._batch_item_streamer._BatchItemStreamer`
   emitter turns core's ``Emitter.on_knot_result`` (ADR WS0b) into the
   stream, so the ``Err``'s full ``ExceptionRecord``, the attempt count and
   the latency ride along from the lineage row. It reads the settings the
   knot was constructed with, so every setting must have been a literal.

   Trade-off, disclosed: ``inputs`` is materialised up front — the resume
   lookup and the item graph need every key before the run starts.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.engine.admission.admission_observer import AdmissionObserver
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.batch._batch_item_streamer import _BatchItemStreamer
from pirn_agents.batch._map_item import _MapItem
from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController
from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.resilience.token_bucket_rate_limiter import TokenBucketRateLimiter


class MapAgent(SubTapestry):
    """Map a per-item agent over a batch, scheduled entirely by the core engine."""

    #: The inner run's execution-plane overrides, resolved by :meth:`process`
    #: and read back by the ``_inner_*`` hooks ``SubTapestry._run_inner``
    #: calls once the graph is built. ``_mutable_``-prefixed: framework slots
    #: written per invocation, never constructor state.
    _mutable_inner_dispatcher: Dispatcher | None = None
    _mutable_inner_concurrency: ConcurrencyLimits | None = None
    _mutable_inner_observers: list[AdmissionObserver] | None = None

    def __init__(
        self,
        *,
        run_item: Callable[[Any], Awaitable[Any]],
        _config: KnotConfig,
        items: Knot | Sequence[Any] | None = None,
        batch_id: Knot | str = "batch",
        concurrency: Knot | int = 8,
        concurrency_group: Knot | str = "map_agent_items",
        timeout: Knot | float | None = None,
        retries: Knot | int = 0,
        retry: KnotRetryPolicy | None = None,
        key_fn: Callable[[Any], str] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        concurrency_controller: AdaptiveConcurrencyController | None = None,
        dispatcher: Dispatcher | None = None,
        admission_observers: Sequence[AdmissionObserver] = (),
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
        **kwargs: Any,
    ) -> None:
        """Wire the batch runner.

        Args:
            run_item: The per-item agent callable — ``async (item) -> output``.
            _config: Framework config; ``id`` names this knot.
            items: The dataset, when wiring this knot into a bigger pipeline —
                a parent ``Knot`` or a literal list/tuple. Unused by the
                standalone :meth:`run`, which takes its inputs there.
            batch_id: Stable id naming this batch. Namespaces every item's
                knot id (``item:<batch_id>:<key>``), which is both its
                admission/lineage identity and its resume key.
            concurrency: Maximum simultaneously in-flight items — the run's
                ``ConcurrencyLimits`` group cap. Must be >= 1. Ignored when
                ``concurrency_controller`` is set (its own limit wins).
            concurrency_group: The ``KnotConfig.concurrency_group`` every
                item is admitted under.
            timeout: Per-item ``KnotConfig.timeout`` in seconds, or ``None``.
            retries: Extra attempts granted to an item that raises (>= 0);
                builds ``KnotRetryPolicy(max_attempts=retries+1)`` when
                ``retry`` is not given.
            retry: A ``KnotRetryPolicy`` overriding ``retries``' default.
            key_fn: Maps an input item to a stable string key. Defaults to
                the item's stream index.
            rate_limiter: A shared token bucket every attempt acquires from.
            concurrency_controller: An AIMD governor bound to
                ``concurrency_group``; its limit seeds the group cap.
            dispatcher: The engine ``Dispatcher`` the items run under;
                ``None`` inherits the ambient run's.
            admission_observers: Extra observers attached to the run.
            history: A ``RunHistory`` to resume from; ``None`` disables
                resume.
            data_store: The value plane for a standalone :meth:`run`; an
                engine-invoked run inherits the enclosing run's.
        """
        super().__init__(
            run_item=run_item,
            items=items,
            batch_id=batch_id,
            concurrency=concurrency,
            concurrency_group=concurrency_group,
            timeout=timeout,
            retries=retries,
            retry=retry,
            key_fn=key_fn,
            rate_limiter=rate_limiter,
            concurrency_controller=concurrency_controller,
            dispatcher=dispatcher,
            admission_observers=admission_observers,
            history=history,
            data_store=data_store,
            _config=_config,
            **kwargs,
        )

    # ------------------------------------------------ engine-invoked path

    async def process(
        self,
        run_item: Callable[[Any], Awaitable[Any]],
        items: Sequence[Any] | None = None,
        batch_id: str = "batch",
        concurrency: int = 8,
        concurrency_group: str = "map_agent_items",
        timeout: float | None = None,
        retries: int = 0,
        retry: KnotRetryPolicy | None = None,
        key_fn: Callable[[Any], str] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        concurrency_controller: AdaptiveConcurrencyController | None = None,
        dispatcher: Any = None,
        admission_observers: Sequence[Any] = (),
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
        **_: Any,
    ) -> Knot:
        """Validate the settings and build the per-item + aggregator graph for this run.

        ``dispatcher`` and ``admission_observers`` are typed ``Any`` here (the
        constructor names their real types): core's ``Dispatcher`` and
        ``AdmissionObserver`` bases carry no pydantic core schema, and ``Knot``
        builds a ``TypeAdapter`` for every annotated ``process()`` parameter
        (see ``_MapItem``'s docstring for the same constraint). They are
        checked with ``isinstance`` instead.

        Returns:
            The ``Aggregator`` (or, when every item already resumed, a tiny
            pass-through sink) whose output is ``list[BatchItemResult]``.

        Raises:
            TypeError: If a setting has the wrong type.
            ValueError: If ``concurrency`` < 1, ``retries`` < 0, or
                ``batch_id`` is empty.
        """
        MapAgent._validate(
            run_item, batch_id, concurrency, retries, dispatcher, admission_observers
        )
        item_list = list(items) if items is not None else []
        resolved_history = history if history is not None else self._mutable_outer_history
        resolved_retry = MapAgent._resolve_retry(retry, retries)
        if concurrency_controller is not None:
            concurrency_controller.bind_to_group(concurrency_group)
        resumed = await MapAgent._resume_lookup(item_list, batch_id, key_fn, resolved_history)
        live_items = len(item_list) - len(resumed)
        self._mutable_inner_dispatcher = dispatcher
        # A group cap with nothing left to run is left undeclared, since naming
        # an unused group only warns (``UnusedConcurrencyGroupWarning``).
        self._mutable_inner_concurrency = (
            ConcurrencyLimits(
                groups={
                    concurrency_group: MapAgent._group_limit(concurrency, concurrency_controller)
                }
            )
            if live_items > 0
            else None
        )
        observers = MapAgent._observers(admission_observers, concurrency_controller)
        self._mutable_inner_observers = observers or None
        return MapAgent._build_graph(
            item_list,
            batch_id,
            resumed,
            run_item=run_item,
            key_fn=key_fn,
            concurrency_group=concurrency_group,
            timeout=timeout,
            retry=resolved_retry,
            rate_limiter=rate_limiter,
            concurrency_controller=concurrency_controller,
        )

    # ------------------------------------ inner-run overrides (core seams)

    def _inner_dispatcher(self) -> Dispatcher | None:
        """This batch's dispatcher; ``None`` inherits the enclosing run's (WS0b)."""
        return self._mutable_inner_dispatcher

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """The group cap the items are admitted under, or ``None`` when nothing runs."""
        return self._mutable_inner_concurrency

    def _inner_admission_observers(self) -> list[AdmissionObserver] | None:
        """The batch's observers (controller included); ``None`` when there are none."""
        return self._mutable_inner_observers

    # ------------------------------------------------------ standalone path

    async def run(
        self, inputs: Iterable[object], *, checkpoint_scope: str | None = None
    ) -> AsyncIterator[BatchItemResult]:
        """Run the agent over ``inputs``, yielding each item's result as it settles.

        Builds a throwaway ``Tapestry`` with a
        :class:`~pirn_agents.batch._batch_item_streamer._BatchItemStreamer`
        emitter attached, starts the item/aggregator graph as a task, and
        yields a ``BatchItemResult`` the moment core's
        ``Emitter.on_knot_result`` reports the item knot settled (ADR WS0b) —
        resumed items first, then live items in completion order. Closing the
        generator early (``break``, ``aclose``) or cancelling its consumer
        cancels the run, and with it every in-flight item.

        The settings are the literal values this knot was constructed with;
        a setting wired to an upstream ``Knot`` only resolves inside an engine
        run, so it cannot drive a standalone one.

        Args:
            inputs: The dataset to map over. Materialised eagerly.
            checkpoint_scope: Namespaces this run's resume key: the effective
                batch id becomes ``f"{batch_id}:{checkpoint_scope}"``.
                ``None`` (the default) uses ``batch_id`` itself.

        Yields:
            One ``BatchItemResult`` per input item.

        Raises:
            TypeError: If ``checkpoint_scope`` is neither ``None`` nor a
                ``str``, or a setting was wired to an upstream ``Knot``.
        """
        if checkpoint_scope is not None and not isinstance(checkpoint_scope, str):
            raise TypeError(
                f"MapAgent.run: checkpoint_scope must be a str or None, "
                f"got {type(checkpoint_scope).__name__}"
            )
        wired = sorted(set(self.parents) - {"items"})
        if wired:
            raise TypeError(
                f"MapAgent.run: settings {wired!r} are wired to upstream knots and only "
                "resolve inside an engine run; construct with literal settings to run standalone"
            )
        settings = self.config_values
        run_item: Callable[[Any], Awaitable[Any]] = settings["run_item"]
        base_batch_id: str = settings["batch_id"]
        concurrency: int = settings["concurrency"]
        retries: int = settings["retries"]
        dispatcher: Dispatcher | None = settings["dispatcher"]
        admission_observers: Sequence[AdmissionObserver] = settings["admission_observers"]
        concurrency_group: str = settings["concurrency_group"]
        key_fn: Callable[[Any], str] | None = settings["key_fn"]
        controller: AdaptiveConcurrencyController | None = settings["concurrency_controller"]
        history: RunHistory | None = settings["history"]
        MapAgent._validate(
            run_item, base_batch_id, concurrency, retries, dispatcher, admission_observers
        )
        if controller is not None:
            controller.bind_to_group(concurrency_group)
        items = list(inputs)
        batch_id = (
            base_batch_id if checkpoint_scope is None else f"{base_batch_id}:{checkpoint_scope}"
        )
        resumed = await MapAgent._resume_lookup(items, batch_id, key_fn, history)
        for index in sorted(resumed):
            yield resumed[index]

        live: dict[str, tuple[int, str]] = {}
        for index, item in enumerate(items):
            if index not in resumed:
                key = MapAgent._key_for(key_fn, index, item)
                live[MapAgent._item_knot_id(batch_id, key)] = (index, key)
        queue: asyncio.Queue[BatchItemResult | None] = asyncio.Queue()
        streamer = _BatchItemStreamer(items_by_knot_id=live, queue=queue)
        run_tapestry = Tapestry(
            history=history,
            data_store=settings["data_store"],
            dispatcher=dispatcher,
            emitters=[streamer],
        )
        run_concurrency = (
            ConcurrencyLimits(
                groups={concurrency_group: MapAgent._group_limit(concurrency, controller)}
            )
            if live
            else None
        )
        with run_tapestry:
            MapAgent._build_graph(
                items,
                batch_id,
                resumed,
                run_item=run_item,
                key_fn=key_fn,
                concurrency_group=concurrency_group,
                timeout=settings["timeout"],
                retry=MapAgent._resolve_retry(settings["retry"], retries),
                rate_limiter=settings["rate_limiter"],
                concurrency_controller=controller,
            )
        # One task: the engine run itself, so the stream below can be drained
        # while the engine schedules the items.  Every item is still admitted,
        # dispatched, timed out and retried by the engine, not here.
        run_task = asyncio.create_task(
            run_tapestry.run(
                RunRequest(concurrency=run_concurrency),
                admission_observers=MapAgent._observers(admission_observers, controller),
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

    @staticmethod
    def _validate(
        run_item: object,
        batch_id: object,
        concurrency: object,
        retries: object,
        dispatcher: object,
        admission_observers: Sequence[object],
    ) -> None:
        """Refuse settings the batch cannot run with (type check, then value check)."""
        if not callable(run_item):
            raise TypeError(f"MapAgent: run_item must be callable, got {type(run_item).__name__}")
        if dispatcher is not None and not isinstance(dispatcher, Dispatcher):
            raise TypeError(
                f"MapAgent: dispatcher must be a Dispatcher or None, got {type(dispatcher).__name__}"
            )
        for observer in admission_observers:
            if not isinstance(observer, AdmissionObserver):
                raise TypeError(
                    f"MapAgent: admission_observers must be AdmissionObservers, "
                    f"got {type(observer).__name__}"
                )
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("MapAgent: batch_id must be a non-empty str")
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
            raise ValueError(f"MapAgent: concurrency must be an int >= 1, got {concurrency!r}")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"MapAgent: retries must be an int >= 0, got {retries!r}")

    @staticmethod
    def _resolve_retry(retry: KnotRetryPolicy | None, retries: int) -> KnotRetryPolicy:
        return retry if retry is not None else KnotRetryPolicy(max_attempts=retries + 1)

    @staticmethod
    def _group_limit(concurrency: int, controller: AdaptiveConcurrencyController | None) -> int:
        return controller.limit() if controller is not None else concurrency

    @staticmethod
    def _observers(
        admission_observers: Sequence[AdmissionObserver],
        controller: AdaptiveConcurrencyController | None,
    ) -> list[AdmissionObserver]:
        observers = list(admission_observers)
        if controller is not None:
            observers.append(controller)
        return observers

    @staticmethod
    def _key_for(key_fn: Callable[[Any], str] | None, index: int, item: object) -> str:
        if key_fn is None:
            return str(index)
        key = key_fn(item)
        if not isinstance(key, str) or not key:
            raise TypeError(f"MapAgent: key_fn must return a non-empty str, got {key!r}")
        return key

    @staticmethod
    async def _resume_lookup(
        items: list[Any],
        batch_id: str,
        key_fn: Callable[[Any], str] | None,
        history: RunHistory | None,
    ) -> dict[int, BatchItemResult]:
        """Return ``{index: BatchItemResult(Skipped)}`` for items already ``Ok`` in *history*."""
        if history is None:
            return {}
        resumed: dict[int, BatchItemResult] = {}
        for index, item in enumerate(items):
            key = MapAgent._key_for(key_fn, index, item)
            item_id = MapAgent._item_knot_id(batch_id, key)
            rows = await history.query_lineage_by_knot_id(item_id)
            if any(row.outcome == "ok" for row in rows):
                resumed[index] = BatchItemResult(
                    index=index,
                    key=key,
                    outcome=Skipped(reason="resumed", detail={"knot_id": item_id}),
                )
        return resumed

    @staticmethod
    def _build_graph(
        items: list[Any],
        batch_id: str,
        resumed: dict[int, BatchItemResult],
        *,
        run_item: Callable[[Any], Awaitable[Any]],
        key_fn: Callable[[Any], str] | None,
        concurrency_group: str,
        timeout: float | None,
        retry: KnotRetryPolicy,
        rate_limiter: TokenBucketRateLimiter | None,
        concurrency_controller: AdaptiveConcurrencyController | None,
    ) -> Knot:
        """Build the per-item knots and their joining ``Aggregator`` (or an all-resumed sink)."""
        on_throttle = (
            concurrency_controller.on_throttle if concurrency_controller is not None else None
        )
        order: list[tuple[str, int, str]] = []
        parents: dict[str, Knot] = {}
        for index, item in enumerate(items):
            if index in resumed:
                continue
            key = MapAgent._key_for(key_fn, index, item)
            parent_key = f"p{index}"
            parents[parent_key] = _MapItem(
                item=item,
                run_item=run_item,
                rate_limiter=rate_limiter,
                on_throttle=on_throttle,
                _config=KnotConfig(
                    id=MapAgent._item_knot_id(batch_id, key),
                    concurrency_group=concurrency_group,
                    timeout=timeout,
                    retry=retry,
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
        total: int, order: list[tuple[str, int, str]], resumed: Mapping[int, BatchItemResult]
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
                by_index[index] = BatchItemResult(index=index, key=key, outcome=inputs[parent_key])
            return [by_index[i] for i in range(total)]

        return combine
