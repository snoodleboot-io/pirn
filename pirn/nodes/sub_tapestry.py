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

    The outer tapestry's history backend is captured at construction time and
    automatically forwarded to inner runs so they appear in the same history
    store and are reachable by the explorer's drill-down navigation.

    Algorithm:
        1. Construction — capture the outer tapestry's history backend (if any)
           so it can be forwarded to the inner run.
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
           outer history is injected so inner run records appear in the same store.
           If the inner run produces any exceptions, ``SubTapestryError`` is raised.
        9. Output extraction — look up the sink knot's output from
           ``run_result.outputs`` using the key returned by
           ``_resolve_output_key(sink)`` and wrap it in ``Ok``.
        10. Error wrapping — any exception escaping steps 3-9 is caught and
            wrapped in ``Err`` so the outer engine sees a normal knot failure.
    """

    _extensible_inner_run: ClassVar[bool] = False

    def _resolve_output_key(self, sink: Knot) -> str:
        """Return the ``run_result.outputs`` key to surface as this knot's value.

        The default uses the sink knot's own ID.  Override in subclasses that
        register their true terminal mid-run (e.g. ``LoopSubTapestry``), where
        the sink returned by ``process()`` is a proxy and the real output lands
        under a different, well-known ID.
        """
        return sink.knot_id

    def __init__(self, **kwargs: Any) -> None:
        # Capture the outer history *before* super().__init__ freezes the object.
        from pirn.tapestry import _current_tapestry

        explicit_tapestry = kwargs.get("tapestry")
        outer = explicit_tapestry or _current_tapestry.get(None)
        outer_history: RunHistory | None = outer.history if outer is not None else None
        super().__init__(**kwargs)
        # Bypass freeze guard to stash history for use in _run_inner.
        object.__setattr__(self, "_mutable_outer_history", outer_history)

    async def process(self, **_: Any) -> Knot:
        """Override to declare the inner pipeline and return its terminal knot.

        Build any knots inside this method — they auto-register into the
        inner tapestry context the base class has already established.
        Return the sink knot whose output becomes this SubTapestry's output.

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
            run_result = await self._run_inner(inner, extensible=self._extensible_inner_run)
            output = run_result.outputs[self._resolve_output_key(sink)]
        except BaseException as exc:
            return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return Ok(value=output)

    async def _run_inner(
        self,
        tapestry: Tapestry,
        *,
        parent_run_id: str | None = None,
        extensible: bool = False,
    ) -> RunResult:
        """Run the inner tapestry and return its ``RunResult``.

        Raises ``SubTapestryError`` if the inner run produces any exceptions.

        The outer tapestry's history is injected automatically so inner runs
        are recorded to the same store.  Pass ``parent_run_id`` to explicitly
        link this inner run to a known outer run_id.
        """
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory
        from pirn.core.run_request import RunRequest
        from pirn.tapestry import _current_history, _current_run_id

        outer_history: RunHistory | None = object.__getattribute__(self, "_mutable_outer_history")
        # Knots constructed dynamically mid-run (outside a `with Tapestry():` block)
        # have no outer history at construction time.  Fall back to the context var
        # set by the enclosing Tapestry.run() call.
        if outer_history is None:
            outer_history = _current_history.get(None)
        # Inject the outer history into the inner tapestry so inner runs are
        # recorded to the same store and appear in the explorer.
        if outer_history is not None and not isinstance(outer_history, InMemoryHistory):
            tapestry._history = outer_history

        # If no explicit parent_run_id was supplied, inherit from the context
        # var set by the enclosing Tapestry.run() call.
        if parent_run_id is None:
            parent_run_id = _current_run_id.get(None)

        result = await tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            extensible=extensible,
        )
        if not result.succeeded:
            raise SubTapestryError(result)
        return result
