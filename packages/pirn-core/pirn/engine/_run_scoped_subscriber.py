"""Run-scoped filter for tapestry-store new-knot notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.tapestry import current_run_id

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class _RunScopedSubscriber:
    """Queues a newly-registered knot only if this run registered it.

    ``Tapestry._store`` is tapestry-scoped and fans every registration to
    every subscriber, but the engine's ``pending_new`` queue is per-run.
    Two concurrent top-level ``run(extensible=True)`` calls on one
    tapestry therefore executed each other's dynamically-registered knots
    -- silently, since the shared parent is in both sheds (PIR-808).

    Ownership is read from the ambient run id at registration time.  That
    is reliable for exactly the reason PIR-802 turned on: run identity
    lives in a ContextVar, so it is already correct per task and survives
    the ``ThreadDispatcher`` hop, which hands off under a copy of the
    caller's context (PIR-767).

    A registration made with **no run in scope** has no owner, so it is
    delivered to every extensible run, exactly as before.  That is the
    external-orchestrator seam: a task created outside ``run()`` never
    inherited a run context, and narrowing it to "nobody" would trade a
    silent-wrong-output bug for a silent-dropped-work one.

    Reading ambient identity requires the store to call subscribers in
    the registering context.  ``InMemoryStore`` does so directly; the
    durable stores deliver from a background LISTEN/pub-sub task and so
    carry the registering run in the notification payload and rebind it
    around dispatch, which restores the same invariant (PIR-815).
    """

    def __init__(self, run_id: str, pending_new: list[Knot]) -> None:
        self._run_id = run_id
        self._pending_new = pending_new

    def __call__(self, knot: Knot) -> None:
        registering_run_id = current_run_id()
        if registering_run_id is None or registering_run_id == self._run_id:
            self._pending_new.append(knot)
