"""``NestedRunKnot`` — a knot that runs nested tapestries from its own ``process()``.

A knot sometimes needs part of its work to run as an inner pipeline — so each
step gets its own lineage row, ``Result``, timeout, retry and admission — while
the knot itself keeps returning a plain value: an atomic ETL knot whose dedup
short-circuit and single final write bracket a fan-out of model calls, say.
``SubTapestry`` cannot host that: its ``__call__`` requires ``process()`` to
return the sink ``Knot`` of *one* inner pipeline and surfaces that sink's output
as its own.  ``NestedRunKnot`` is the seam underneath it: everything a nested
run needs to belong to the run that started it, with no contract on what
``process()`` returns.  ``SubTapestry`` is a ``NestedRunKnot`` that adds the
sink-returning contract; a plain knot subclasses ``NestedRunKnot`` directly (or
mixes it in beside a marker base such as ``Assembler``) and awaits
``self._run_inner(tapestry)`` wherever it needs an inner run::

    class Summaries(NestedRunKnot):
        async def process(self, texts: tuple[str, ...], **_: Any) -> list[str]:
            with Tapestry() as inner:
                parts = {f"s{i}": Summarize(text=t, _config=KnotConfig(id=f"s{i}"))
                         for i, t in enumerate(texts)}
                joined = Aggregator(combine=..., _config=KnotConfig(id="joined"), **parts)
            run = await self._run_inner(inner)
            return run.outputs["joined"]

What an inner run inherits:

* **Observability and value plane** — the enclosing run's history, emitters
  (with their error policy), data store, transport and traceback filter, so
  inner rows land in the same store, reach the same subscribers, and name
  values that resolve (PIR-764/834/837, PIR-725).
* **Execution plane** — dispatcher, admission gate and ``ConcurrencyLimits``,
  admission observers, replay posture and identity resolver, inherited by
  ``Tapestry.run`` for everything the inner tapestry did not name (ADR
  agents-speaks-core, WS0b).  Per-container overrides are the
  ``_inner_dispatcher`` / ``_inner_concurrency`` /
  ``_inner_admission_observers`` hooks or the matching ``_run_inner`` keyword
  arguments.
* **Nesting** — each inner run is a child frame of the enclosing run's
  ``RunNesting``, keyed by :meth:`_nesting_key`, so the depth cap and the
  re-entry guard apply.
* **Identity** — the inner run records this knot as its ``parent_knot_id`` and
  the enclosing run as its ``parent_run_id``; this knot's lineage row records
  the inner run ids (``extra["inner_run_id"]``, and ``extra["inner_run_ids"]``
  in start order once there is more than one).

Admission.  A nested-run knot is a *container*: it holds no admission slot
(``_holds_admission_slot`` is ``False``), because its inner leaves are admitted
through the very gate it would otherwise be holding a slot of — under
``max_in_flight=1`` that is a deadlock.  It therefore may not declare a
``concurrency_group`` (refused at construction), and a dispatcher may route it
somewhere other than its leaves (``Dispatcher.dispatcher_for_container``).  Any
work ``process()`` does outside its inner runs is not metered by the gate; put
work that must be metered inside an inner run.

Algorithm:
    1. Construction — capture the enclosing tapestry's history, emitter
       subscription (list and policy) and value plane, as the fallback for an
       inner run started outside any engine run; refuse a
       ``concurrency_group``.
    2. ``process()`` builds an inner tapestry and awaits ``_run_inner``.
    3. ``_run_inner`` reads the live context (set by the enclosing
       ``Tapestry.run``) for history, value plane, emitters and traceback
       filter, falling back to the construction-time capture, and applies
       them to the inner tapestry.
    4. It resolves the per-container execution-plane overrides (argument,
       then hook, then inherit) and starts the inner run with this knot as its
       parent knot, its nesting key, and the run's ordinal among this knot's
       inner runs — the index an inherited replay posture uses to pick the
       matching recorded inner run.
    5. It records the inner run ids for ``lineage_extra`` and raises
       ``SubTapestryError`` when the inner run failed, unless
       ``_inner_failures_reach_sink`` says the failures were delivered to a
       sink that consumes them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_context_vars import RunContextVars
from pirn.nodes.sub_tapestry_error import SubTapestryError

if TYPE_CHECKING:
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
    from pirn.core.run_result import RunResult
    from pirn.core.transport.data_transport import DataTransport
    from pirn.emitters.emitter import Emitter
    from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
    from pirn.engine.admission.admission_observer import AdmissionObserver
    from pirn.engine.dispatchers.dispatcher import Dispatcher
    from pirn.tapestry import Tapestry


class NestedRunKnot(Knot):
    """Base for knots whose ``process()`` runs nested tapestries through ``_run_inner``.

    Subclass it (or mix it in after a marker base: ``class X(Assembler,
    NestedRunKnot)``) and implement ``process()`` as for any knot — any return
    type.  Build an inner ``Tapestry`` inside ``process()`` and await
    ``self._run_inner(inner)`` for its ``RunResult``; call it as many times as
    the work needs.  See the module docstring for what an inner run inherits.

    Set ``_inner_failures_reach_sink = True`` on a subclass whose inner sink
    receives its parents' ``Result`` values (``ErrorPolicy.RECEIVE_ERRORS``) so an
    inner knot's failure is the sink's input rather than a ``SubTapestryError``.
    """

    #: When ``True``, an inner run in which some knot failed does not fail this
    #: knot as long as the sink produced a value: the failures were delivered
    #: to the sink -- wired with ``ErrorPolicy.RECEIVE_ERRORS`` -- which is what
    #: it exists to combine (a fan-out over tool calls reporting each call's
    #: ``Ok | Err | Skipped`` beside its siblings; ADR agents-speaks-core,
    #: WS1).  The failed knots are still recorded in the inner run's history
    #: and lineage.  Off by default: an inner failure the sink did not receive
    #: is this knot's ``Err``.
    _inner_failures_reach_sink: ClassVar[bool] = False

    # A container holds no admission slot: its inner run's leaves are admitted
    # through the enclosing run's own gate (ADR agents-speaks-core, WS0b).
    _holds_admission_slot: ClassVar[bool] = False

    def _nesting_key(self) -> str:
        """Return the key the nested-run guard tracks this container by.

        The qualified class name and this knot's id: a nested run whose path
        already holds it is *this container* re-entering itself, which
        ``RunNesting.child`` refuses when a ``max_nesting_depth`` is active
        (``NestedRunCycleError``).  The id is part of the key on purpose
        (ADR agents-speaks-core, WS1): two *different* instances of one
        container class nested in each other — an agent handing a task to
        another agent of the same class — are not a cycle, while the same
        instance reached again down its own inner pipeline is.  A container
        that has a better identity than its id (an agent-as-tool call keyed
        by the agent it wraps) overrides this.
        """
        return f"{type(self).__module__}.{type(self).__qualname__}:{self.knot_id}"

    def _inner_dispatcher(self) -> Dispatcher | None:
        """Return the dispatcher the inner run executes on, or ``None`` to inherit.

        The default inherits the enclosing run's dispatcher (or the inner
        tapestry's own, when ``process()`` built it with one).  Override in a
        subclass whose inner work must run on a particular backend
        regardless of what the outer run uses.
        """
        return None

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """Return the inner run's ``ConcurrencyLimits``, or ``None`` to inherit.

        The default shares the enclosing run's admission gate, so the outer
        caps bound the inner leaves too.  Override to give the inner run a
        *bounded* budget of its own (e.g. ``ConcurrencyLimits(max_in_flight=2)``)
        and its gate is chained under the enclosing run's: admission takes a
        ticket from both, so the inner cap and the outer cap both apply
        (PIR-870).  An explicitly unbounded ``ConcurrencyLimits()`` is the one
        case that is not chained -- it opts the inner run out of any cap at
        all, including the enclosing one.
        """
        return None

    def _inner_admission_observers(self) -> list[AdmissionObserver] | None:
        """Return the inner run's ``AdmissionObserver``s, or ``None`` to inherit.

        With a shared gate the enclosing run's observers hear inner
        admissions anyway; observers returned here are added ahead of them.
        """
        return None

    @staticmethod
    def inherited_emitters(
        own: list[Emitter], inherited: list[Emitter] | None
    ) -> list[Emitter] | None:
        """Combine an inner tapestry's own emitters with those inherited from the outer run.

        Returns ``None`` when there is nothing to inherit.  ``None`` is what
        ``Tapestry.run(emitters=...)`` reads as "not overridden", so the inner
        tapestry keeps whatever subscription it already had — which is also the
        right answer when the outer run deliberately opted out with
        ``run(emitters=[])``.

        De-duplicated by identity, not equality: the same emitter instance
        registered on both the outer tapestry and the inner one must receive one
        ``on_lineage`` call per record, not two.  Equality is the wrong test
        because emitters are ordinary objects whose ``__eq__`` may be identity-
        based, value-based, or expensive.

        Args:
            own: Emitters the inner tapestry already carries, in declared order.
            inherited: Emitters the enclosing run is fanning to, or ``None`` when
                there is no enclosing run.

        Returns:
            The merged list, or ``None`` to leave the inner subscription alone.
        """
        if not inherited:
            return None
        merged = list(own)
        seen = {id(emitter) for emitter in merged}
        merged.extend(emitter for emitter in inherited if id(emitter) not in seen)
        return merged

    def __init__(self, **kwargs: Any) -> None:
        # Capture the outer observability wiring *before* super().__init__
        # freezes the object.  History and emitters are captured together
        # because they are two halves of the same subscription: forwarding one
        # without the other is what made inner work visible to the explorer and
        # invisible to spans/metrics/logs (PIR-834).

        explicit_tapestry = kwargs.get("tapestry")
        outer = explicit_tapestry or RunContextVars.tapestry.get(None)
        outer_history: RunHistory | None = outer.history if outer is not None else None
        outer_emitters: list[Emitter] | None = outer.emitters if outer is not None else None
        outer_emitter_policy: EmitterErrorPolicy | None = (
            outer.emitter_error_policy if outer is not None else None
        )
        # The value plane follows the history for the reason given on
        # Tapestry.adopt_value_plane: a lineage row and the value its
        # output_hash names have to live in stores that answer each other.
        outer_data_store: DataStore | None = outer.data_store if outer is not None else None
        outer_transport: DataTransport | None = outer.transport if outer is not None else None
        # A container holds no admission slot (see ``_holds_admission_slot``),
        # so a group tag on it would name a slot it never takes: refuse it
        # before registration rather than let a cap silently apply to
        # nothing (WS0b).
        config = kwargs.get("_config")
        if isinstance(config, KnotConfig) and config.concurrency_group is not None:
            raise ValueError(
                f"{type(self).__name__}({config.id!r}): a container knot holds no admission "
                f"slot, so it cannot join concurrency group {config.concurrency_group!r}; "
                "put the group on the knots inside its inner tapestry instead"
            )
        super().__init__(**kwargs)
        # Knot.__setattr__ already exempts any `_mutable_`-prefixed name from
        # the freeze guard, so a plain assignment is enough here — no need to
        # bypass __setattr__ via object.__setattr__ as well.
        self._mutable_outer_history = outer_history
        self._mutable_outer_emitters = outer_emitters
        self._mutable_outer_emitter_policy = outer_emitter_policy
        self._mutable_outer_data_store = outer_data_store
        self._mutable_outer_transport = outer_transport
        self._mutable_inner_run_meta: dict[str, Any] = {}
        # Reassigned, never mutated: a run-scoped copy shares this tuple with
        # the graph knot until its first inner run replaces it (PIR-809).
        self._mutable_inner_run_ids: tuple[str, ...] = ()

    def lineage_extra(self) -> dict[str, Any]:
        return {**super().lineage_extra(), **self._mutable_inner_run_meta}

    def _make_inner_tapestry(self) -> Tapestry:
        """Return a fresh tapestry for ``process()`` to build an inner pipeline into.

        The default is a bare ``Tapestry()``; the outer run's history, emitters,
        value plane and traceback filter are forwarded onto it by
        ``_run_inner`` regardless.  Override to give the inner run a setting
        only the container can know -- a ``max_nesting_depth`` for a knot that
        runs a nested agent, ``concurrency`` limits for a knot that fans tool
        calls out under a group, a fallback ``traceback_filter`` -- without
        opening a second tapestry inside ``process()`` (ADR agents-speaks-core,
        WS1).  Whatever ``_run_inner`` inherits from the enclosing run still
        wins over a setting made here, as it does for the default.
        """
        from pirn.tapestry import Tapestry

        return Tapestry()

    def _reset_inner_runs(self) -> None:
        """Forget the inner runs recorded so far, before a fresh invocation."""
        self._mutable_inner_run_meta = {}
        self._mutable_inner_run_ids = ()

    def _record_inner_run_meta(self, run_result: RunResult) -> None:
        """Publish the latest inner run's identifiers for ``lineage_extra`` to surface.

        ``inner_run_id`` / ``inner_knot_count`` / ``inner_failures`` describe
        the most recent inner run; ``inner_run_ids`` lists every inner run this
        invocation started, in start order, once there is more than one — the
        index an inherited replay posture resolves an inner run's recording by.
        """
        meta: dict[str, Any] = {
            "inner_run_id": run_result.run_id,
            "inner_knot_count": len(run_result.lineage),
            "inner_failures": len(run_result.exceptions),
        }
        if len(self._mutable_inner_run_ids) > 1:
            meta["inner_run_ids"] = list(self._mutable_inner_run_ids)
        self._mutable_inner_run_meta = meta

    async def _run_inner(
        self,
        tapestry: Tapestry,
        *,
        parent_run_id: str | None = None,
        extensible: bool = False,
        dispatcher: Dispatcher | None = None,
        concurrency: ConcurrencyLimits | None = None,
        admission_observers: list[AdmissionObserver] | None = None,
    ) -> RunResult:
        """Run the inner tapestry and return its ``RunResult``.

        Raises ``SubTapestryError`` if the inner run produces any exceptions.

        The outer tapestry's history, emitters *and* value plane — its data
        store and transport — are injected automatically, so inner runs are
        recorded to the same store, fan their status, lineage and run-result
        events to the same subscribers, and write their outputs where the
        lineage rows they produce can be resolved.  Pass ``parent_run_id`` to
        explicitly link this inner run to a known outer run_id.  See
        ``Tapestry.adopt_value_plane`` for why the data store is forwarded
        unconditionally and the transport is not.

        The outer run's *execution plane* — dispatcher, admission gate and
        ``ConcurrencyLimits``, admission observers, replay posture, identity
        resolver — is inherited by ``Tapestry.run`` itself for everything
        the inner tapestry did not name (ADR agents-speaks-core, WS0b), so a
        ``ThreadDispatcher`` outer run keeps its inner leaves on worker
        threads, and an outer ``max_in_flight`` or group cap bounds inner
        leaves against the *same* budget.  ``dispatcher``, ``concurrency``
        and ``admission_observers`` override that per call; when omitted,
        the ``_inner_dispatcher`` / ``_inner_concurrency`` /
        ``_inner_admission_observers`` hooks decide, and their default
        (``None``) inherits.  Naming a *bounded* ``concurrency`` gives the
        inner run a gate chained under the outer budget -- both apply
        (PIR-870); naming an explicitly unbounded ``ConcurrencyLimits()``
        opts the inner run out of the outer budget entirely.

        Every inner run is recorded on this knot (``_record_inner_run_meta``)
        whether it succeeded or failed, in start order, so the lineage row
        this knot writes names each one.

        Emitter forwarding is unconditional — there is no volume guard, and
        that is deliberate.  ``RunRetention`` (PIR-765) bounds *history*
        because ``InMemoryHistory`` is the default backend, so an open-ended
        ``LoopSubTapestry`` would otherwise grow an ephemeral store without
        limit that nobody asked for.  Emitters have no default instance: every
        one present was attached by an operator who asked to observe this
        pipeline, and the events an inner run produces are proportional to work
        it actually did.  Suppressing them would recreate exactly the defect
        this forwarding fixes, one nesting level down.  An emitter that needs
        to bound its own intake can filter on ``RunResult.parent_run_id`` /
        ``run_path``, which identify inner runs precisely.  See PIR-834.
        """
        from pirn.core.run_request import RunRequest

        # Prefer the live contextvar over the construction-time capture.
        #
        # `__init__` captures the history of whatever tapestry was ambient when
        # this knot was built.  For a container constructed inside another
        # container's `process()`, that ambient tapestry is the throwaway inner
        # tapestry the enclosing container opened — so the capture is a fresh
        # default store which is discarded once the parent's inner run
        # completes, and every record written to it is lost.  It is non-None but
        # wrong, which is why the old `is None` fallback never fired.
        #
        # The contextvar is set by the enclosing `Tapestry.run()` to the store
        # that run is actually writing to, so it is right at every depth.  It is
        # None only outside a run, and the construction-time capture is then the
        # correct answer.  See PIR-764.
        outer_history: RunHistory | None = RunContextVars.history.get(None)
        if outer_history is None:
            outer_history = self._mutable_outer_history
        # Inject the outer history into the inner tapestry so inner runs are
        # recorded to the same store and appear in the explorer.
        if outer_history is not None:
            tapestry.adopt_history(outer_history)

        # The value plane rides the same two-source dance as the history, and
        # for the same reason: a container built inside another container's
        # `process()` captured the throwaway inner tapestry at construction
        # time, whose data store is a fresh InMemoryDataStore about to be thrown
        # away.  Reading the contextvar first means a nested container writes
        # its values into the *real* outer store, so the lineage row it records
        # in the real outer history has something to resolve against
        # (PIR-764/PIR-773, PIR-837).
        outer_data_store: DataStore | None = RunContextVars.data_store.get(None)
        if outer_data_store is None:
            outer_data_store = self._mutable_outer_data_store
        outer_transport: DataTransport | None = RunContextVars.transport.get(None)
        if outer_transport is None:
            outer_transport = self._mutable_outer_transport
        tapestry.adopt_value_plane(data_store=outer_data_store, transport=outer_transport)

        # Emitters follow history through the same two-source dance, and for the
        # same reason: a container built inside another container's `process()`
        # captured the throwaway inner tapestry at construction time, which
        # carries no emitters at all.  Reading the contextvar first means a
        # nested container inherits the *real* outer subscription rather than
        # the throwaway's empty one (PIR-764/PIR-773).
        #
        # The list and the policy are read as a pair from whichever source wins:
        # a policy belongs to the subscription it governs, so mixing a live
        # emitter list with a construction-time policy (or vice versa) would
        # apply one run's error handling to another run's emitters.
        outer_emitters: list[Emitter] | None = RunContextVars.emitters.get(None)
        outer_emitter_policy: EmitterErrorPolicy | None = RunContextVars.emitter_error_policy.get(
            None
        )
        if outer_emitters is None:
            outer_emitters = self._mutable_outer_emitters
            outer_emitter_policy = self._mutable_outer_emitter_policy
        inner_emitters = self.inherited_emitters(tapestry.emitters, outer_emitters)
        # Only carry the outer policy when emitters actually came with it;
        # otherwise leave the inner tapestry governed by its own default.
        inner_emitter_policy = outer_emitter_policy if inner_emitters is not None else None

        # If no explicit parent_run_id was supplied, inherit from the context
        # var set by the enclosing Tapestry.run() call.
        if parent_run_id is None:
            parent_run_id = RunContextVars.run_id.get(None)

        # Per-container overrides of the inherited execution plane (WS0b): an
        # explicit argument wins, then the subclass hook; ``None`` inherits.
        inner_dispatcher = dispatcher if dispatcher is not None else self._inner_dispatcher()
        inner_limits = concurrency if concurrency is not None else self._inner_concurrency()
        inner_observers = (
            admission_observers
            if admission_observers is not None
            else self._inner_admission_observers()
        )
        request = RunRequest(concurrency=inner_limits)
        # This run's place among this knot's inner runs: an inherited replay
        # posture serves it from the recorded inner run at the same index.
        ordinal = len(self._mutable_inner_run_ids)
        self._mutable_inner_run_ids = (*self._mutable_inner_run_ids, request.run_id)
        # Inherit the enclosing run's traceback filter.  Without this the inner
        # run records its own exceptions unfiltered, and since nested runs became
        # durable (PIR-764/765) a credential in an inner traceback is persisted
        # verbatim — redacted in the outer record, leaked in the inner one.
        # See PIR-725.
        result = await tapestry.run(
            request,
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            _nesting_key=self._nesting_key(),
            _inner_run_ordinal=ordinal,
            extensible=extensible,
            traceback_filter=RunContextVars.traceback_filter.get(None),
            emitters=inner_emitters,
            emitter_error_policy=inner_emitter_policy,
            dispatcher=inner_dispatcher,
            admission_observers=inner_observers,
        )
        self._record_inner_run_meta(result)
        if not result.succeeded and not self._inner_failures_reach_sink:
            raise SubTapestryError(result)
        return result
