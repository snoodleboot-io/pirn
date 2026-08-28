"""SubTapestry — a knot whose execution body is a complete inner tapestry.

Subclass ``SubTapestry`` and implement ``process(**kwargs) -> Knot``.  Inside
``process``, build the inner pipeline using any knots and primitives.
Knots auto-register into the inner tapestry via the active context.
Return the terminal (sink) knot — its output becomes this knot's output.

The resolved values of outer parent knots arrive as plain Python values
in ``**kwargs``, exactly like any other knot.  Use them as constants
when constructing the inner pipeline.

Example::

    class ScorePipeline(SubTapestry):
        async def process(self, raw: pd.DataFrame, threshold: float, **_: Any) -> Knot:
            cleaned = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
            return ScoreKnot(
                data=cleaned, threshold=threshold, _config=KnotConfig(id="score")
            )

    pipeline = ScorePipeline(
        raw=upstream_knot,
        threshold=0.9,
        _config=KnotConfig(id="score-pipeline"),
    )

The base ``__call__`` establishes the inner tapestry context before invoking
``process()``, runs the inner graph, and surfaces the sink knot's output as
this knot's output.  ``SubTapestryError`` is raised if the inner run fails;
``Knot.__call__`` wraps it as ``Err`` so the outer pipeline sees a normal failure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ValidationError

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.managers.exception_record import ExceptionRecord

if TYPE_CHECKING:
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


def _inherited_emitters(own: list[Any], inherited: list[Any] | None) -> list[Any] | None:
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


def _apply_inherited_value_plane(
    tapestry: Tapestry,
    *,
    data_store: Any,
    transport: Any,
) -> None:
    """Point an inner tapestry at the enclosing run's value plane.

    The *value plane* is the pair a run writes its outputs into: the
    ``DataStore`` that holds each value by content hash, and the
    ``DataTransport`` that moves it between edges.  An inner tapestry is
    constructed with defaults, so without this its values go to a fresh
    ``InMemoryDataStore`` that is discarded the moment the inner run ends —
    while the inner *lineage* rows, written to the forwarded outer history, keep
    advertising ``output_hash`` values that now resolve against nothing
    (PIR-837).

    The two halves are not treated identically, because they are not the same
    kind of thing:

    * **The data store is forwarded unconditionally**, exactly as the history
      is.  A lineage row and the value it names are two halves of one record;
      routing the row to the outer history while routing the value elsewhere
      recreates the dangling reference this fixes.  Whoever owns the history
      owns the store that answers it.
    * **The transport yields to an inner tapestry that chose its own.**  A
      transport is a movement layer inside a single run, not part of any
      durable record: its handles never leave the run that created them and no
      lineage row references one.  Inheriting it keeps a disk- or object-store-
      backed pipeline from silently dropping to ``InlineTransport`` inside a
      ``SubTapestry`` body, which is where the bulk of a pipeline's data often
      moves.  But a ``LoopSubTapestry`` iteration built as
      ``Tapestry(transport=...)`` inside ``step()`` named that transport
      deliberately, and overwriting it would be the same silent override in the
      opposite direction.

    Sharing one transport instance across the outer and inner runs is safe:
    every ``DataTransport`` method is keyed by ``run_id``, and the inner run has
    its own, so ``begin_run`` / ``end_run`` allocate and release inner-run
    resources without touching the outer run's.  Sharing one data store is safe
    for a different reason: it is content-addressed, so an inner value that
    collides with an outer one is the same value.

    Args:
        tapestry: The inner tapestry about to be run.
        data_store: The enclosing run's data store, or ``None`` when there is
            no enclosing run to inherit from.
        transport: The enclosing run's transport, or ``None`` likewise.
    """
    if data_store is not None:
        tapestry._data_store = data_store
    if transport is not None and not tapestry._transport_explicit:
        tapestry._transport = transport


class SubTapestryError(Exception):
    """Raised when the inner tapestry pipeline fails.

    Attached to the ``Err`` the outer pipeline receives so the inner
    ``RunResult`` is reachable for inspection.
    """

    def __init__(self, inner_result: RunResult) -> None:
        self.inner_result = inner_result
        exception_count = len(inner_result.exceptions)
        super().__init__(
            f"inner pipeline failed with {exception_count} exception(s); run_id={inner_result.run_id!r}"
        )


class SubTapestry(Knot):
    """Base class for knots whose execution is a complete inner tapestry pipeline.

    Set ``_extensible_inner_run = True`` on a subclass to run the inner tapestry
    in extensible mode, where knots may be registered mid-run.  Override
    ``_resolve_output_key`` to redirect the output lookup to a knot whose ID
    differs from the sink returned by ``process()`` (e.g. a mid-run terminal).

    Subclass and implement ``process(**kwargs) -> Knot``.  Build the inner
    pipeline inside ``process()`` and return the terminal (sink) knot.
    The base class establishes the tapestry context, runs the graph, and
    surfaces the sink's output as this knot's output.

    Inputs are wired exactly like any other knot: Knot-valued kwargs
    become parents resolved by the outer engine; non-Knot kwargs become
    config constants.  Both arrive as plain resolved values in ``process``.

    The outer tapestry's observability wiring — its history backend, its
    emitters, the error policy governing them, and the value plane its records
    point into (data store and transport) — is captured at construction time and
    forwarded to inner runs.  Inner runs therefore appear in the same history
    store, reachable by the explorer's drill-down navigation, fan their status,
    lineage and run-result events to the same emitters, and write their outputs
    into the same data store, so an inner ``KnotLineage`` row's ``output_hash``
    resolves.  All of it travels together on purpose: forwarding history alone
    left the two observability planes disagreeing, so a knot moved into a
    SubTapestry body looked fully traced in the explorer while silently losing
    every span, metric and log line it used to produce (PIR-834) — and its
    recorded output hash named a value nobody could fetch (PIR-837).

    Algorithm:
        1. Construction — capture the outer tapestry's history backend, emitter
           subscription and value plane (if any) so they can be forwarded to
           the inner run.
        2. Outer engine invocation — ``__call__`` receives resolved parent values
           and config constants as ``parent_results``.
        3. Fan-out short-circuit — if mapped inputs are declared, delegate to
           ``_fan_out`` and return immediately; no inner tapestry is started.
        4. Input validation — if ``config.validate_io`` is set, validate all
           inputs through the knot's Pydantic input model before proceeding.
        5. Inner tapestry context — open a fresh ``Tapestry`` context manager
           so that every knot constructed inside ``process()`` auto-registers
           into the inner graph.
        6. ``process()`` call — invoke the subclass implementation, which builds
           the inner pipeline and returns the terminal (sink) knot.
        7. Sink validation — assert the returned value is a ``Knot`` instance and
           (for non-extensible runs) that it was registered in the inner tapestry.
        8. Inner run — call ``_run_inner`` to execute the inner tapestry.  The
           outer history, emitters and value plane are injected so inner run
           records appear in the same store, inner events reach the same
           subscribers, and inner values land where those records point.
           If the inner run produces any exceptions, ``SubTapestryError`` is raised.
        9. Output extraction — look up the sink knot's output from
           ``run_result.outputs`` using the key returned by
           ``_resolve_output_key(sink)`` and wrap it in ``Ok``.
        10. Error wrapping — any exception escaping steps 3-9 is caught and
            wrapped in ``Err`` so the outer engine sees a normal knot failure.
    """

    _extensible_inner_run: ClassVar[bool] = False

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    def _resolve_output_key(self, sink: Knot) -> str:
        """Return the ``run_result.outputs`` key to surface as this knot's value.

        The default uses the sink knot's own ID.  Override in subclasses that
        register their true terminal mid-run (e.g. ``LoopSubTapestry``), where
        the sink returned by ``process()`` is a proxy and the real output lands
        under a different, well-known ID.
        """
        return sink.knot_id

    def __init__(self, **kwargs: Any) -> None:
        # Capture the outer observability wiring *before* super().__init__
        # freezes the object.  History and emitters are captured together
        # because they are two halves of the same subscription: forwarding one
        # without the other is what made inner work visible to the explorer and
        # invisible to spans/metrics/logs (PIR-834).
        from pirn.tapestry import _current_tapestry

        explicit_tapestry = kwargs.get("tapestry")
        outer = explicit_tapestry or _current_tapestry.get(None)
        outer_history: RunHistory | None = outer.history if outer is not None else None
        outer_emitters: list[Any] | None = outer.emitters if outer is not None else None
        outer_emitter_policy: Any = outer.emitter_error_policy if outer is not None else None
        # The value plane follows the history for the reason given on
        # _apply_inherited_value_plane: a lineage row and the value its
        # output_hash names have to live in stores that answer each other.
        outer_data_store: Any = outer.data_store if outer is not None else None
        outer_transport: Any = outer.transport if outer is not None else None
        super().__init__(**kwargs)
        # Bypass freeze guard to stash fields that are unknown until after
        # __init__ completes.  All follow the _mutable_ convention so the
        # freeze guard allows them.
        object.__setattr__(self, "_mutable_outer_history", outer_history)
        object.__setattr__(self, "_mutable_outer_emitters", outer_emitters)
        object.__setattr__(self, "_mutable_outer_emitter_policy", outer_emitter_policy)
        object.__setattr__(self, "_mutable_outer_data_store", outer_data_store)
        object.__setattr__(self, "_mutable_outer_transport", outer_transport)
        object.__setattr__(self, "_mutable_inner_run_meta", {})

    def lineage_extra(self) -> dict[str, Any]:
        return {**super().lineage_extra(), **self._mutable_inner_run_meta}

    async def process(self, *args: Any, **kwargs: Any) -> Knot:
        """Override to declare the inner pipeline and return its terminal knot.

        Build any knots inside this method — they auto-register into the
        inner tapestry context the base class has already established.
        Return the sink knot whose output becomes this SubTapestry's output.

        An override still names its own inputs and still must return a
        ``Knot``: the gradual ``*args`` here relaxes only the parameter half of
        the override check (PIR-833), and ``__init_subclass__`` refuses an
        override that actually declares ``*args``.

        Raises:
            NotImplementedError: Always; subclasses must override this method.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Framework entry point — invoked by the engine.

        Establishes the inner tapestry context, resolves inputs, calls
        ``process()``, validates the returned sink knot, runs the inner
        graph, and returns the sink's output wrapped in ``Ok``.
        """
        from pirn.tapestry import Tapestry

        config = self._mutable_config
        kwargs: dict[str, Any] = dict(self._mutable_config_values)
        kwargs.update(parent_results)

        if self._mutable_mapped_inputs:
            try:
                outputs = await self._fan_out(kwargs)
            except BaseException as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))
            return Ok(value=outputs)

        if config.validate_io:
            try:
                kwargs = self._validate_inputs(kwargs)
            except ValidationError as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))

        # Clear the previous invocation's metadata up front.  It used to be
        # assigned only after the try body succeeded, so a failed inner run left
        # the *previous* run's inner_run_id in place for lineage to report.
        self._mutable_inner_run_meta = {}

        try:
            with Tapestry() as inner:
                sink = await self.process(**kwargs)
            if not isinstance(sink, Knot):
                raise TypeError(
                    f"{type(self).__name__}.process() must return a Knot; got {type(sink).__name__}"
                )
            # For extensible runs the true terminal is registered mid-run, so the
            # sink returned by process() may not yet be in the inner tapestry.
            if not self._extensible_inner_run and inner.get(sink.knot_id) is None:
                raise ValueError(
                    f"{type(self).__name__}.process() returned a Knot not registered "
                    "in the inner tapestry — was it built outside the process() body?"
                )
            try:
                run_result = await self._run_inner(inner, extensible=self._extensible_inner_run)
            except SubTapestryError as exc:
                # Record the metadata for the run that failed.  Without this the
                # failure path reports no inner_run_id at all, leaving a sibling's
                # Ok record in the same inner run with no retrieval path.
                self._record_inner_run_meta(exc.inner_result)
                raise
            self._record_inner_run_meta(run_result)
            output = run_result.outputs[self._resolve_output_key(sink)]
        except BaseException as exc:
            return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return Ok(value=output)

    def _record_inner_run_meta(self, run_result: RunResult) -> None:
        """Publish the inner run's identifiers for ``lineage_extra`` to surface."""
        self._mutable_inner_run_meta = {
            "inner_run_id": run_result.run_id,
            "inner_knot_count": len(run_result.lineage),
            "inner_failures": len(run_result.exceptions),
        }

    async def _run_inner(
        self,
        tapestry: Tapestry,
        *,
        parent_run_id: str | None = None,
        extensible: bool = False,
    ) -> RunResult:
        """Run the inner tapestry and return its ``RunResult``.

        Raises ``SubTapestryError`` if the inner run produces any exceptions.

        The outer tapestry's history, emitters *and* value plane — its data
        store and transport — are injected automatically, so inner runs are
        recorded to the same store, fan their status, lineage and run-result
        events to the same subscribers, and write their outputs where the
        lineage rows they produce can be resolved.  Pass ``parent_run_id`` to
        explicitly link this inner run to a known outer run_id.  See
        ``_apply_inherited_value_plane`` for why the data store is forwarded
        unconditionally and the transport is not.

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
        from pirn.tapestry import (
            _current_data_store,
            _current_emitter_error_policy,
            _current_emitters,
            _current_history,
            _current_run_id,
            _current_traceback_filter,
            _current_transport,
        )

        # Prefer the live contextvar over the construction-time capture.
        #
        # `__init__` captures the history of whatever tapestry was ambient when
        # this knot was built.  For a SubTapestry constructed inside another
        # SubTapestry's `process()`, that ambient tapestry is the throwaway
        # `with Tapestry() as inner:` opened by `__call__` below — so the capture
        # is a fresh default store which is discarded once the parent's inner run
        # completes, and every record written to it is lost.  It is non-None but
        # wrong, which is why the old `is None` fallback never fired.
        #
        # The contextvar is set by the enclosing `Tapestry.run()` to the store
        # that run is actually writing to, so it is right at every depth.  It is
        # None only outside a run, and the construction-time capture is then the
        # correct answer.  See PIR-764.
        outer_history: RunHistory | None = _current_history.get(None)
        if outer_history is None:
            outer_history = object.__getattribute__(self, "_mutable_outer_history")
        # Inject the outer history into the inner tapestry so inner runs are
        # recorded to the same store and appear in the explorer.
        if outer_history is not None:
            tapestry._history = outer_history

        # The value plane rides the same two-source dance as the history, and
        # for the same reason: a SubTapestry built inside another SubTapestry's
        # `process()` captured the throwaway `with Tapestry() as inner:` at
        # construction time, whose data store is a fresh InMemoryDataStore about
        # to be thrown away.  Reading the contextvar first means a nested
        # SubTapestry writes its values into the *real* outer store, so the
        # lineage row it records in the real outer history has something to
        # resolve against (PIR-764/PIR-773, PIR-837).
        outer_data_store: Any = _current_data_store.get(None)
        if outer_data_store is None:
            outer_data_store = object.__getattribute__(self, "_mutable_outer_data_store")
        outer_transport: Any = _current_transport.get(None)
        if outer_transport is None:
            outer_transport = object.__getattribute__(self, "_mutable_outer_transport")
        _apply_inherited_value_plane(
            tapestry, data_store=outer_data_store, transport=outer_transport
        )

        # Emitters follow history through the same two-source dance, and for the
        # same reason: a SubTapestry built inside another SubTapestry's
        # `process()` captured the throwaway `with Tapestry() as inner:` at
        # construction time, which carries no emitters at all.  Reading the
        # contextvar first means a nested SubTapestry inherits the *real* outer
        # subscription rather than the throwaway's empty one (PIR-764/PIR-773).
        #
        # The list and the policy are read as a pair from whichever source wins:
        # a policy belongs to the subscription it governs, so mixing a live
        # emitter list with a construction-time policy (or vice versa) would
        # apply one run's error handling to another run's emitters.
        outer_emitters: list[Any] | None = _current_emitters.get(None)
        outer_emitter_policy: Any = _current_emitter_error_policy.get(None)
        if outer_emitters is None:
            outer_emitters = object.__getattribute__(self, "_mutable_outer_emitters")
            outer_emitter_policy = object.__getattribute__(self, "_mutable_outer_emitter_policy")
        inner_emitters = _inherited_emitters(tapestry.emitters, outer_emitters)
        # Only carry the outer policy when emitters actually came with it;
        # otherwise leave the inner tapestry governed by its own default.
        inner_emitter_policy = outer_emitter_policy if inner_emitters is not None else None

        # If no explicit parent_run_id was supplied, inherit from the context
        # var set by the enclosing Tapestry.run() call.
        if parent_run_id is None:
            parent_run_id = _current_run_id.get(None)

        # Inherit the enclosing run's traceback filter.  Without this the inner
        # run records its own exceptions unfiltered, and since nested runs became
        # durable (PIR-764/765) a credential in an inner traceback is persisted
        # verbatim — redacted in the outer record, leaked in the inner one.
        # See PIR-725.
        result = await tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            extensible=extensible,
            traceback_filter=_current_traceback_filter.get(None),
            emitters=inner_emitters,
            emitter_error_policy=inner_emitter_policy,
        )
        if not result.succeeded:
            raise SubTapestryError(result)
        return result
