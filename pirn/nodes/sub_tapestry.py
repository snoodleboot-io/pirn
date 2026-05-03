"""SubTapestry — a knot whose execution body is a complete inner tapestry.

Subclass ``SubTapestry`` and implement ``process(**kwargs)``.  Inside
``process``, construct an inner ``Tapestry``, build the pipeline, and
return ``await self._run_inner(inner_tapestry)``.

The resolved values of outer parent knots arrive as plain Python values
in ``**kwargs``, exactly like any other knot.  Use them as constants
when constructing the inner pipeline.

Example::

    class ScorePipeline(SubTapestry):
        async def process(self, raw: pd.DataFrame, threshold: float, **_: Any) -> RunResult:
            with Tapestry() as inner:
                cleaned = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
                scored  = ScoreKnot(
                    data=cleaned, threshold=threshold, _config=KnotConfig(id="score")
                )
            return await self._run_inner(inner)

    pipeline = ScorePipeline(
        raw=upstream_knot,
        threshold=0.9,
        _config=KnotConfig(id="score-pipeline"),
    )

``_run_inner`` raises ``SubTapestryError`` if the inner run fails, which
``Knot.__call__`` catches and wraps as ``Err``.  The outer pipeline sees
a normal failure; the inner ``RunResult`` is attached to the error for
inspection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.core.knot import Knot

if TYPE_CHECKING:
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.run_result import RunResult
    from pirn.tapestry import Tapestry


class SubTapestryError(Exception):
    """Raised by ``_run_inner`` when the inner tapestry pipeline fails.

    Caught by ``Knot.__call__`` and converted to ``Err``.
    """

    def __init__(self, inner_result: RunResult) -> None:
        self.inner_result = inner_result
        n = len(inner_result.exceptions)
        super().__init__(
            f"inner pipeline failed with {n} exception(s); run_id={inner_result.run_id!r}"
        )


class SubTapestry(Knot):
    """Base class for knots whose execution is a complete inner tapestry pipeline.

    Subclass and implement ``process(**kwargs) -> RunResult``.  Build and
    run the inner tapestry using ``_run_inner(tapestry)``.

    Inputs are wired exactly like any other knot: Knot-valued kwargs
    become parents resolved by the outer engine; non-Knot kwargs become
    config constants.  Both arrive as plain resolved values in ``process``.

    The outer tapestry's history backend is captured at construction time and
    automatically forwarded to inner runs so they appear in the same history
    store and are reachable by the explorer's drill-down navigation.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Capture the outer history *before* super().__init__ freezes the object.
        from pirn.tapestry import _CURRENT_TAPESTRY

        explicit_tapestry = kwargs.get("tapestry")
        outer = explicit_tapestry or _CURRENT_TAPESTRY.get(None)
        outer_history: RunHistory | None = outer.history if outer is not None else None
        super().__init__(**kwargs)
        # Bypass freeze guard to stash history for use in _run_inner.
        object.__setattr__(self, "_mutable_outer_history", outer_history)

    async def process(self, **_: Any) -> Any:
        """Override in subclasses to build and run an inner tapestry pipeline and return its RunResult.

        Returns:
            RunResult from the inner tapestry pipeline built and executed by the subclass implementation.

        Raises:
            NotImplementedError: Always; subclasses must override this method.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

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
        from pirn.tapestry import _CURRENT_HISTORY, _CURRENT_RUN_ID

        outer_history: RunHistory | None = object.__getattribute__(self, "_mutable_outer_history")
        # Knots constructed dynamically mid-run (outside a `with Tapestry():` block)
        # have no outer history at construction time.  Fall back to the context var
        # set by the enclosing Tapestry.run() call.
        if outer_history is None:
            outer_history = _CURRENT_HISTORY.get(None)
        # Inject the outer history into the inner tapestry so inner runs are
        # recorded to the same store and appear in the explorer.
        if outer_history is not None and not isinstance(outer_history, InMemoryHistory):
            tapestry._history = outer_history

        # If no explicit parent_run_id was supplied, inherit from the context
        # var set by the enclosing Tapestry.run() call.
        if parent_run_id is None:
            parent_run_id = _CURRENT_RUN_ID.get(None)

        result = await tapestry.run(
            RunRequest(),
            _parent_run_id=parent_run_id,
            _parent_knot_id=self.knot_id,
            extensible=extensible,
        )
        if not result.succeeded:
            raise SubTapestryError(result)
        return result
