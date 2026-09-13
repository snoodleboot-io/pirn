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
  ``AdmissionGate``/``ReadyQueue`` every other knot in the framework is
  scheduled through, not a private semaphore.
* **Per-item timeout/retry** is ``KnotConfig.timeout`` / ``KnotConfig.retry``
  (a ``KnotRetryPolicy``) on each item's knot — ``GovernedDispatch``'s job,
  not a hand-rolled ``run_with_retries``.
* **Resume-after-crash** is a ``RunHistory`` lineage query: an item's knot id
  is ``item:<batch_id>:<key>``, stable across runs, so a re-run with the same
  ``history=`` skips any item whose id already has an ``Ok`` lineage row. No
  checkpoint store is written or read.
* **Dispatcher choice** (Local/Thread/Ray/Dask) and **adaptive admission
  feedback** are the inner run's own ``dispatcher=``/``admission_observers=``.

Two ways to use it, matching the two things a ``Knot`` can be:

1. **Wired into a bigger pipeline** — pass ``items=`` a parent ``Knot`` (or a
   literal list) at construction; the engine calls this knot like any other,
   and its single output is the ``list[BatchItemResult]`` the aggregator
   combined.
2. **Standalone** — :meth:`run` is the one-cycle deprecation shim preserving
   the pre-migration ``async for result in map_agent.run(inputs)`` contract:
   it builds a throwaway ``Tapestry``, runs the same item/aggregator graph to
   completion, and yields each ``BatchItemResult``.

   Trade-off, disclosed: the pre-migration :meth:`run` streamed each result
   the instant it settled and pulled the input iterable lazily, so a batch
   never had to be resident in memory at once. An ``Aggregator`` only
   produces its combined value once *every* parent has settled, so this
   :meth:`run` now yields its whole batch at the end of one engine run
   instead of incrementally, and materialises ``inputs`` up front. A future
   workstream restoring incremental streaming needs either a per-item
   ``Emitter`` that also resolves each ``Err``'s full ``ExceptionRecord``
   mid-run (today only available from the final ``RunResult.exceptions``) or
   a ``LoopSubTapestry``-based redesign; see the ADR proposal's WS4 note.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry, current_tapestry

from pirn_agents.batch._map_item import _MapItem
from pirn_agents.batch._resumed_batch import _ResumedBatch
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
                steers that cap live via the run's ``AdmissionGate``.
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

    # ------------------------------------------------ engine-invoked path

    async def process(self, items: Any = None, **_: Any) -> Knot:
        """Build the per-item + aggregator graph and apply this run's admission settings.

        Args:
            items: The resolved dataset — whatever the constructor's
                ``items=`` (a parent knot's output, or the literal passed
                through) resolved to. Must be a list/tuple.

        Returns:
            The ``Aggregator`` (or, when every item already resumed, a tiny
            pass-through sink) whose output is ``list[BatchItemResult]``.
        """
        inner = current_tapestry()
        item_list = list(items) if items is not None else []
        history = (
            self._mutable_history
            if self._mutable_history is not None
            else self._mutable_outer_history
        )
        resumed = await self._resume_lookup(item_list, self._mutable_batch_id, history)
        if inner is not None:
            self._apply_run_settings(inner, live_items=len(item_list) - len(resumed))
        return self._build_graph(item_list, self._mutable_batch_id, resumed)

    def _apply_run_settings(self, tapestry: Tapestry, *, live_items: int) -> None:
        """Point *tapestry* at this batch's dispatcher, group cap, and observers.

        ``SubTapestry`` forwards the enclosing run's history/data store/
        emitters into its inner tapestry automatically (``_run_inner``), but
        not its dispatcher or concurrency limits — those are set here,
        directly on the inner tapestry this knot's ``process()`` is already
        running inside, the same way ``SubTapestry`` itself reaches into a
        tapestry's private fields to forward the value plane.

        Args:
            tapestry: The inner tapestry to configure.
            live_items: How many items will actually be dispatched (total
                minus resumed). A concurrency group with nothing left to run
                is left undeclared, since naming an unused group only warns
                (``UnusedConcurrencyGroupWarning``) but is needless noise for
                the common "everything already resumed" case.
        """
        if live_items > 0:
            tapestry._concurrency = ConcurrencyLimits(
                groups={self._mutable_concurrency_group: self._effective_group_limit()}
            )
        if self._mutable_dispatcher is not None:
            tapestry._dispatcher = self._mutable_dispatcher
        observers = self._observers_for_run()
        if observers:
            tapestry._admission_observers = observers

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
        """Run the agent over ``inputs`` to completion, yielding each item's result.

        One-cycle deprecation shim preserving the pre-migration streaming
        contract (see the module docstring for the disclosed streaming
        trade-off). Builds a throwaway ``Tapestry``, runs the item/aggregator
        graph once, and yields the combined ``list[BatchItemResult]``.

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
        run_tapestry = Tapestry(
            history=history,
            data_store=self._mutable_data_store,
            dispatcher=self._mutable_dispatcher,
        )
        live_items = len(items) - len(resumed)
        run_concurrency = (
            ConcurrencyLimits(
                groups={self._mutable_concurrency_group: self._effective_group_limit()}
            )
            if live_items > 0
            else None
        )
        with run_tapestry:
            sink = self._build_graph(items, batch_id, resumed)
            run_result = await run_tapestry.run(
                RunRequest(concurrency=run_concurrency),
                admission_observers=self._observers_for_run(),
            )
        await run_tapestry.close()
        combined: list[BatchItemResult] = run_result.outputs[sink.knot_id]
        for item_result in combined:
            yield item_result

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
            return _ResumedBatch(resumed=combine(), _config=KnotConfig(id=f"{batch_id}:aggregate"))
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
