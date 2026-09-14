"""``ExecutionPlane`` — the scheduling half of a run, published for inner runs to inherit.

A run has two planes an inner run must share with it.  The *observability
and value plane* — history, data store, transport, emitters, traceback
filter — was forwarded into ``SubTapestry`` / ``LoopSubTapestry`` inner runs
by PIR-764/834/837.  The *execution plane* is the other half: **how** the
run's knots are scheduled and attributed — the ``Dispatcher`` they run on,
the ``AdmissionGate`` that meters them (and the ``ConcurrencyLimits`` it
enforces), the ``AdmissionObserver``s that hear every admission, the
``ReplaySession`` the run is served from, and the ``IdentityResolver`` that
names its actor.  Before this seam an inner tapestry applied only its own
defaults: a ``LocalDispatcher`` under a ``ThreadDispatcher`` outer run, an
unbounded gate under a capped one, no observers, no replay, a re-resolved
actor (ADR agents-speaks-core, WS0b; PIR-841 slice 3).

``Tapestry.run`` publishes the plane it is running under on a context
variable for the run's duration, and derives an inner run's plane from the
enclosing one: everything the inner tapestry did not name itself is
inherited.  The gate is inherited **by identity** — the same instance, so
``max_in_flight`` and every group cap are one budget across the whole run
tree, not one budget per run.  A slot held by an inner knot is a slot the
outer run cannot hand to anyone else.

Algorithm:
    ``Tapestry.run`` resolves the plane of the run about to start:

    1. Read the enclosing plane from the context variable (``None`` for a
       root run).
    2. *Dispatcher*: the ``run(dispatcher=)`` argument, else the tapestry's
       own dispatcher when it was passed to ``Tapestry(...)`` explicitly,
       else the enclosing plane's, else the tapestry's default.
    3. *Gate and limits*: when the request or the tapestry names *bounded*
       ``ConcurrencyLimits``, the run gets a gate chained under the
       enclosing plane's gate (``ChainedAdmissionGate``, PIR-870) -- both
       budgets apply, released together.  Naming explicitly *unbounded*
       ``ConcurrencyLimits()`` still gets an independent, unchained gate --
       the documented way to opt a run out of the enclosing budget entirely.
       Otherwise the run shares the enclosing plane's gate and reports the
       enclosing limits.  A root run without limits gets the unbounded
       gate.
    4. *Observers*: the ``run(admission_observers=)`` argument, else the
       tapestry's own; when the gate is inherited the enclosing plane's
       observers are appended, de-duplicated by identity, because an
       observer belongs to the gate it steers.
    5. *Replay*: the ``run(replay=)`` argument, else — when the enclosing
       run is in replay posture — the recording of the inner run the
       container knot's own recorded row names (``extra["inner_run_id"]``),
       loaded from this run's history; ``None`` when the container has no
       recorded row, so a container the session lets execute live runs
       its inner pipeline live too.
    6. *Identity resolver*: the tapestry's own when passed explicitly, else
       the enclosing plane's, else the tapestry's default chain.
    7. Publish the resolved plane for the run's duration.

    A process-boundary dispatcher (Ray, Dask, Celery) starts from an empty
    context, so an inner run executing on a remote worker inherits nothing
    and behaves as a root run — the same honest answer as for emitters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
    from pirn.core.identity.identity_resolver import IdentityResolver
    from pirn.engine.admission.admission_gate import AdmissionGate
    from pirn.engine.admission.admission_observer import AdmissionObserver
    from pirn.engine.dispatchers.dispatcher import Dispatcher
    from pirn.recording.replay_session import ReplaySession


@dataclass(frozen=True, slots=True)
class ExecutionPlane:
    """What a run is scheduled on, metered by, watched by, served from and attributed to.

    Immutable; one per run, built by ``Tapestry.run`` and published on
    ``pirn.tapestry._current_execution_plane`` for the run's duration so an
    inner run can inherit it.  Read yours with :meth:`current`.

    Attributes:
        dispatcher: The ``Dispatcher`` the run's knots execute on.
        gate: The ``AdmissionGate`` metering the run.  Shared by identity
            with every inner run that declares no limits of its own.
        limits: The ``ConcurrencyLimits`` the gate enforces, or ``None`` for
            an unbounded gate.  Reported alongside the gate so an inner run
            sharing it can fail fast on a knot in a group the limits do not
            define, exactly as the root run does.
        admission_observers: The observers hearing the gate's admissions
            and releases, in notification order.
        replay: The ``ReplaySession`` the run is served from, or ``None``
            when it executes live.
        identity_resolver: The resolver that names the run's actor when the
            ``RunRequest`` carries none.
    """

    dispatcher: Dispatcher
    gate: AdmissionGate
    limits: ConcurrencyLimits | None
    admission_observers: tuple[AdmissionObserver, ...]
    replay: ReplaySession | None
    identity_resolver: IdentityResolver

    @staticmethod
    def current() -> ExecutionPlane | None:
        """Return the plane of the enclosing run, or ``None`` outside a run.

        The value is the plane of the **innermost** run in progress: inside a
        ``SubTapestry`` body it is the inner run's plane, which shares the
        outer gate unless the inner tapestry named its own limits.
        """
        from pirn.tapestry import _current_execution_plane

        return _current_execution_plane.get(None)
