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

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.nodes.sub_tapestry_error import SubTapestryError

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class SubTapestry(NestedRunKnot):
    """Base class for knots whose execution is a complete inner tapestry pipeline.

    Set ``_extensible_inner_run = True`` on a subclass to run the inner tapestry
    in extensible mode, where knots may be registered mid-run.  Set
    ``_inner_failures_reach_sink = True`` on a subclass whose sink receives its
    parents' ``Result`` values (``ErrorPolicy.RECEIVE_ERRORS``) so an inner knot's
    failure is the sink's input rather than this knot's ``Err``.  Override
    ``_resolve_output_key`` to redirect the output lookup to a knot whose ID
    differs from the sink returned by ``process()`` (e.g. a mid-run terminal).

    Subclass and implement ``process(**kwargs) -> Knot``.  Build the inner
    pipeline inside ``process()`` and return the terminal (sink) knot.
    The base class establishes the tapestry context, runs the graph, and
    surfaces the sink's output as this knot's output.

    Inputs are wired exactly like any other knot: Knot-valued kwargs
    become parents resolved by the outer engine; non-Knot kwargs become
    config constants.  Both arrive as plain resolved values in ``process``.

    Everything that makes an inner run belong to the enclosing one — the
    construction-time capture, ``_run_inner``, the ``_inner_*`` hooks, the
    nesting key and the slot-free admission — is inherited from
    :class:`~pirn.nodes.nested_run_knot.NestedRunKnot`; ``SubTapestry`` adds
    only the contract that ``process()`` returns the sink of one inner
    pipeline whose output becomes this knot's.  A knot that needs inner runs
    but returns its own value subclasses ``NestedRunKnot`` instead.

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
        5. Inner tapestry context — open the tapestry ``_make_inner_tapestry``
           returns (a bare ``Tapestry()`` by default) as a context manager so
           that every knot constructed inside ``process()`` auto-registers
           into the inner graph.
        6. ``process()`` call — invoke the subclass implementation, which builds
           the inner pipeline and returns the terminal (sink) knot.
        7. Sink validation — assert the returned value is a ``Knot`` instance and
           (for non-extensible runs) that it was registered in the inner tapestry.
        8. Inner run — call ``_run_inner`` to execute the inner tapestry.  The
           outer history, emitters and value plane are injected so inner run
           records appear in the same store, inner events reach the same
           subscribers, and inner values land where those records point.
           The outer *execution plane* — dispatcher, admission gate and
           limits, admission observers, replay posture, identity resolver —
           is inherited by ``Tapestry.run`` itself for everything the inner
           tapestry did not name (ADR agents-speaks-core, WS0b); the
           ``_inner_dispatcher`` / ``_inner_concurrency`` /
           ``_inner_admission_observers`` hooks, or the matching
           ``_run_inner`` keyword arguments, override it per container.
           If the inner run produces any exceptions, ``SubTapestryError`` is raised.
        8a. Admission — this knot itself holds no admission slot while step 8
            runs (``_holds_admission_slot`` is ``False``): its inner run shares
            the enclosing run's gate, so a slot held here would be one its own
            leaves could deadlock on.  A container therefore may not declare a
            ``concurrency_group``; step 1 refuses one with ``ValueError``.
        9. Output extraction — look up the sink knot's output from
           ``run_result.outputs`` using the key returned by
           ``_resolve_output_key(sink)`` and wrap it in ``Ok``.  A sink the
           inner run *skipped* (a closed ``Gate`` upstream of it) makes this
           knot ``Skipped`` with the sink's own ``skip_reason``, marked
           ``propagates`` so every knot downstream of this container records
           that same reason rather than the engine's generic
           ``"parent_failed_or_skipped"``; never an ``Err`` over the missing
           output.  When ``_inner_failures_reach_sink`` is set and the sink
           produced neither a value nor a skip, the inner run's failure is this
           knot's ``SubTapestryError`` after all -- the flag tolerates failures
           the sink *received*, not a sink that failed itself.
        10. Error wrapping — any exception escaping steps 3-9 is caught and
            wrapped in ``Err`` so the outer engine sees a normal knot failure,
            except a cancellation of the task itself, which propagates
            (``Knot._is_task_cancellation``, PIR-849).
    """

    _extensible_inner_run: ClassVar[bool] = False

    # A container in every renderer: the Mermaid subroutine shape, the HTML
    # explorer's drill-down node.  Inherited by ``LoopSubTapestry`` and every
    # other subclass; see ``Knot._knot_kind``.
    _knot_kind: ClassVar[str] = "sub_tapestry"

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

    async def process(self, *args: Any, **_: Any) -> Knot:
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

        config = self._mutable_config
        prepared = await self._prepare_inputs(parent_results)
        if not isinstance(prepared, dict):
            return prepared
        kwargs = prepared

        # Clear the previous invocation's metadata up front.  It used to be
        # assigned only after the try body succeeded, so a failed inner run left
        # the *previous* run's inner_run_id in place for lineage to report.
        self._reset_inner_runs()

        try:
            with self._make_inner_tapestry() as inner:
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
            # ``_run_inner`` records the run on this knot whether it succeeded
            # or failed, so a failed inner run still names its inner_run_id and
            # a sibling's Ok record in it keeps a retrieval path.
            run_result = await self._run_inner(inner, extensible=self._extensible_inner_run)
            output_key = self._resolve_output_key(sink)
            if (
                not run_result.succeeded
                and self._inner_failures_reach_sink
                and output_key not in run_result.outputs
                and output_key not in run_result.skipped
            ):
                # ``_inner_failures_reach_sink`` tolerates an inner failure
                # *because the sink consumed it*.  With no sink output and no
                # sink skip, nothing consumed anything: the run simply failed,
                # and letting it through produced a ``KeyError`` on the missing
                # output one line below, reported as this knot's error instead of
                # the real one (PIR-873).
                raise SubTapestryError(run_result)
            if output_key in run_result.skipped:
                # The sink deliberately produced no value -- a closed ``Gate``
                # on the way to it, a non-selected ``Branch`` arm -- so this
                # container produced none either.  Its own outcome is that
                # skip, not a ``KeyError`` on the missing output (ADR
                # agents-speaks-core, WS1: a denied tool call is ``Skipped``
                # all the way out of the invocation that wraps it).
                # ``propagates`` so the inner reason survives outward: without
                # it every knot downstream of this container recorded the
                # engine's generic ``"parent_failed_or_skipped"`` and an inner
                # ``approval_denied`` was unreadable one hop away (PIR-873).
                return Skipped(
                    reason=self._sink_skip_reason(run_result, output_key), propagates=True
                )
            output = run_result.outputs[output_key]
        except BaseException as exc:
            # A real cancellation of this task propagates, like ``Knot.__call__``
            # (PIR-849): the inner run has already been cancelled and wound
            # down by its own engine, and the outer engine must see the
            # cancellation rather than a failed result.
            if self._is_task_cancellation(exc):
                raise
            return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return Ok(value=output)

    @staticmethod
    def _sink_skip_reason(run_result: RunResult, output_key: str) -> str:
        """The lineage ``skip_reason`` recorded for *output_key*, or ``"skipped"``."""
        for row in run_result.lineage:
            if row.knot_id == output_key and row.skip_reason:
                return row.skip_reason
        return "skipped"
