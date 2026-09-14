"""``RunContextVars`` — the context variables a run publishes for what it executes."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.backends.base.tapestry_store import TapestryStore
    from pirn.core.execution_plane import ExecutionPlane
    from pirn.core.run_nesting import RunNesting
    from pirn.core.transport.data_transport import DataTransport
    from pirn.emitters.emitter import Emitter
    from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
    from pirn.tapestry import Tapestry


class RunContextVars:
    """The ambient state a ``Tapestry`` publishes on ``contextvars``.

    Every variable is task-local under asyncio and survives a thread hop made
    under a copy of the context (``ThreadDispatcher``); a process-boundary
    dispatcher starts from an empty context and so inherits nothing.  Each
    defaults to ``None``, which means "no enclosing run" (or, for
    :attr:`tapestry`, "no ``with Tapestry():`` block").

    Framework code reads and sets these directly; application code should
    prefer the typed accessors that wrap them (``Tapestry.current()``,
    ``Tapestry.current_run_id()``, ``Tapestry.current_emitters()``,
    ``RunNesting.current()``, ``ExecutionPlane.current()``).

    Attributes:
        tapestry: The tapestry of the active ``with Tapestry():`` block.
            Knots constructed inside the block auto-register with it.
        run_id: The run id of the currently-executing run.  Set by
            ``Tapestry.run()`` so a nested run links to its parent without
            ``process()`` having to know it.
        history: The history of the currently-executing run.  A container
            constructed mid-run (outside any ``with Tapestry():`` block) still
            inherits the outer history and records its inner runs there.
        emitters: The emitter list the enclosing run fans events to, so a
            knot inside a ``SubTapestry`` body reaches the same emitters as a
            top-level knot (PIR-834).  ``None`` is distinct from an empty list:
            ``run(emitters=[])`` is an explicit opt-out an inner run honours.
        emitter_error_policy: The policy the enclosing run applies when one of
            its emitters raises; read as a pair with :attr:`emitters`.
        data_store: The data store the enclosing run writes knot outputs into,
            so an inner value lands in the store its lineage row references
            (PIR-837).
        transport: The transport the enclosing run moves values over.  Unlike
            the data store it yields to an inner tapestry that named its own
            (``Tapestry.adopt_value_plane``).  See PIR-837.
        traceback_filter: The traceback filter the enclosing run uses, so one
            filter set at the top covers the whole run tree (PIR-725).
        nesting: The nested-run frame of the enclosing run — depth, enclosing
            run ids, container keys and the tightest depth cap.  Read it with
            ``RunNesting.current()`` (ADR agents-speaks-core, WS0).
        execution_plane: The execution plane of the enclosing run — dispatcher,
            admission gate and limits, observers, replay posture and identity
            resolver.  Read it with ``ExecutionPlane.current()`` (WS0b).
        store: The store of the currently-executing *extensible* run, so a
            knot can register newcomers mid-run via ``Tapestry.current_store()``.
            ``None`` in non-extensible runs.
        dispatching_knot_id: The id of the knot the engine is executing in the
            current task.  A mid-run registration reads it to learn which knot
            registered the newcomer, which fixes the newcomer's place in the
            run's reported order (PIR-841).
    """

    tapestry: ClassVar[ContextVar[Tapestry | None]] = ContextVar(
        "pirn_current_tapestry", default=None
    )
    run_id: ClassVar[ContextVar[str | None]] = ContextVar("pirn_current_run_id", default=None)
    history: ClassVar[ContextVar[RunHistory | None]] = ContextVar(
        "pirn_current_history", default=None
    )
    emitters: ClassVar[ContextVar[list[Emitter] | None]] = ContextVar(
        "pirn_current_emitters", default=None
    )
    emitter_error_policy: ClassVar[ContextVar[EmitterErrorPolicy | None]] = ContextVar(
        "pirn_current_emitter_error_policy", default=None
    )
    data_store: ClassVar[ContextVar[DataStore | None]] = ContextVar(
        "pirn_current_data_store", default=None
    )
    transport: ClassVar[ContextVar[DataTransport | None]] = ContextVar(
        "pirn_current_transport", default=None
    )
    traceback_filter: ClassVar[ContextVar[Callable[[str], str] | None]] = ContextVar(
        "pirn_current_traceback_filter", default=None
    )
    nesting: ClassVar[ContextVar[RunNesting | None]] = ContextVar(
        "pirn_current_nesting", default=None
    )
    execution_plane: ClassVar[ContextVar[ExecutionPlane | None]] = ContextVar(
        "pirn_current_execution_plane", default=None
    )
    store: ClassVar[ContextVar[TapestryStore | None]] = ContextVar(
        "pirn_current_store", default=None
    )
    dispatching_knot_id: ClassVar[ContextVar[str | None]] = ContextVar(
        "pirn_current_dispatching_knot_id", default=None
    )
