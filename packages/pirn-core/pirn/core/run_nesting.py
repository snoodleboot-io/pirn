"""``RunNesting`` — where a run sits in the tree of nested runs, and how deep it may go.

Every ``Tapestry.run()`` executes under one immutable frame.  A root run's
frame is depth ``0``; a run started by a container knot (``SubTapestry``,
``LoopSubTapestry``'s loop run, each loop iteration) is the *child* of the
enclosing run's frame: one level deeper, carrying the enclosing run ids and
the *nesting keys* of the container knots on the way down.  The frame
travels on a context variable, so it is inherited by inner runs wherever the
container executes — including a ``ThreadDispatcher`` worker, which runs under
a copy of the caller's context — and is empty on a process-boundary dispatcher
(Ray, Dask, Celery), where nothing ambient survives.

The frame is also the nested-run guard (ADR agents-speaks-core, WS0).  When
any tapestry on the path set ``max_nesting_depth``, entering a run deeper
than the tightest cap raises ``NestingDepthExceededError``, and a container
instance re-entering itself — its nesting key already on the path — raises
``NestedRunCycleError`` at once rather than after burning the whole budget.
Both are raised inside the container knot's execution, so the outer engine
records them as that knot's ``Err``.  With no cap anywhere on the path the
guard is off and nesting is unbounded, exactly as before the frame existed.

Algorithm:
    ``child(key, parent_run_id, max_depth=own)`` for the run about to start:

    1. ``limit`` is the tighter of the inherited cap and the starting
       tapestry's own cap (``None`` when neither is set).
    2. ``depth' = depth + 1``; if ``limit`` is set and ``depth' > limit``,
       raise ``NestingDepthExceededError``.
    3. If ``limit`` is set, ``key`` is given and ``key in path``, raise
       ``NestedRunCycleError``.
    4. Return the frame ``(depth', run_ids + (parent_run_id,),
       path + (key,) if key else path, limit)``.

    ```text
    root:        depth=0  run_ids=()        path=()             max_depth=own
    SubTapestry: depth=1  run_ids=(r0,)     path=(Sub,)         max_depth=min(inherited, own)
    Loop run:    depth=2  run_ids=(r0,r1)   path=(Sub,Loop)
    iteration:   depth=3  run_ids=(r0,r1,r2) path=(Sub,Loop)    # iterations add no key
    ```

    A loop iteration counts one level of depth (it is a real run with its own
    id) but adds no key: the loop's own class is already on the path, and a
    loop nested inside another loop's iteration is not a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn.core.run_context_vars import RunContextVars
from pirn.exceptions.nested_run_cycle_error import NestedRunCycleError
from pirn.exceptions.nesting_depth_exceeded_error import NestingDepthExceededError


@dataclass(frozen=True, slots=True)
class RunNesting:
    """Immutable position of a run in the nested-run tree.

    Attributes:
        depth: How many runs enclose this one; ``0`` for a root run.
        run_ids: Ids of the enclosing runs, outermost first.
        path: Nesting keys of the container knots between the root and this
            run, outermost first.  Loop iterations contribute no key.
        max_depth: The tightest ``max_nesting_depth`` on the path, or
            ``None`` when no tapestry on the path set one (guard off).
    """

    depth: int = 0
    run_ids: tuple[str, ...] = ()
    path: tuple[str, ...] = ()
    max_depth: int | None = None

    @staticmethod
    def current() -> RunNesting:
        """Return the frame of the run executing in this context.

        Outside any run this is the root frame (depth ``0``).  Inside a knot's
        ``process()`` it is the frame of the run that dispatched the knot, so a
        knot that starts nested work can read how deep it already is.
        """

        frame = RunContextVars.nesting.get(None)
        return frame if frame is not None else RunNesting()

    @property
    def guarded(self) -> bool:
        """Whether a depth cap is active on this path."""
        return self.max_depth is not None

    def child(
        self, key: str | None, parent_run_id: str, *, max_depth: int | None = None
    ) -> RunNesting:
        """Return the frame for a run nested directly under this one.

        Args:
            key: Nesting key of the container knot starting the run — its
                qualified class name and knot id (``SubTapestry._nesting_key``)
                — or ``None`` for a run that should count toward depth but
                not toward cycle detection (a loop iteration).
            parent_run_id: Id of the run this frame belongs to, which becomes
                the innermost entry of the child's ``run_ids``.
            max_depth: The starting tapestry's own ``max_nesting_depth``;
                combined with the inherited cap by taking the tighter.

        Returns:
            The child frame.

        Raises:
            NestingDepthExceededError: If the child would be deeper than the
                tightest cap on the path.
            NestedRunCycleError: If a cap is active and *key* is already on
                the path.
        """
        caps = [cap for cap in (self.max_depth, max_depth) if cap is not None]
        limit = min(caps) if caps else None
        depth = self.depth + 1
        if limit is not None and depth > limit:
            raise NestingDepthExceededError(depth=depth, limit=limit, path=self.path, key=key)
        if limit is not None and key is not None and key in self.path:
            raise NestedRunCycleError(key=key, path=self.path)
        return RunNesting(
            depth=depth,
            run_ids=(*self.run_ids, parent_run_id),
            path=(*self.path, key) if key is not None else self.path,
            max_depth=limit,
        )

    def run_path(self, run_id: str) -> str:
        """Return the materialised path of *run_id* under this frame.

        ``/{run_id}`` for a root run, ``/{outer}/.../{run_id}`` for a nested
        one — the format ``RunResult.run_path`` documents.
        """
        return "/" + "/".join((*self.run_ids, run_id))
