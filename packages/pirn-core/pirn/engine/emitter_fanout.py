"""``EmitterFanout`` — wires a run's emitters to its status/lineage/result streams.

Extracted out of ``Engine`` (a pure move, PIR-856): neither method reads or
writes any ``Engine`` instance state, so both are ``@staticmethod``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.engine._emitter_subscriber import _EmitterSubscriber

if TYPE_CHECKING:
    from pirn.core.run_context import RunContext
    from pirn.managers.status_event import StatusEvent

_log = logging.getLogger(__name__)


class EmitterFanout:
    """Stateless helpers that fan a run's events out to its emitters."""

    @staticmethod
    def handle_emitter_error(
        emitter: Any,
        event_type: str,
        exc: Exception,
        policy: EmitterErrorPolicy,
    ) -> None:
        """Apply ``policy`` to an exception an emitter raised handling ``event_type``."""
        if policy is EmitterErrorPolicy.IGNORE:
            return
        if policy is EmitterErrorPolicy.WARN:
            _log.warning("emitter %r failed on %s: %s", emitter, event_type, exc)
            return
        # RAISE
        raise exc

    @staticmethod
    def subscribe_emitters_to_status(
        ctx: RunContext,
        emitters: list[Any],
        emitter_error_policy: EmitterErrorPolicy,
    ) -> None:
        """Subscribe each emitter's ``on_status`` to ``StatusManager``.

        StatusManager calls subscribers synchronously; emitters are
        async.  We schedule each call as a fire-and-forget task on the
        running loop. A failing ``on_status`` is routed through
        ``handle_emitter_error`` — the same policy dispatch used for
        ``on_lineage``/``on_run_result`` — so IGNORE/WARN/RAISE apply here
        too, instead of being swallowed unconditionally regardless of the
        configured policy.
        """
        loop = asyncio.get_running_loop()
        # Strong-reference the in-flight tasks; without this, Python's
        # GC may reclaim them before they complete. ctx.emitter_tasks
        # lives as long as the run.
        emitter_tasks = ctx.emitter_tasks

        for emitter in emitters:
            ctx.status.subscribe(
                _EmitterSubscriber(
                    emitter,
                    loop,
                    emitter_tasks,
                    emitter_error_policy,
                    EmitterFanout.handle_emitter_error,
                )
            )

    @staticmethod
    async def emit_status(
        event: StatusEvent,
        *,
        emitters: Sequence[Any] | None = None,
        policy: EmitterErrorPolicy | None = None,
    ) -> None:
        """Deliver one ad hoc ``StatusEvent`` to a run's emitters.

        ``subscribe_emitters_to_status`` exists because ``StatusManager.
        transition`` is a *synchronous* call made from inside the engine's
        scheduling loop, so its subscribers must be scheduled as
        fire-and-forget tasks rather than awaited in place. Code that already
        runs inside an async knot's ``process()`` — an LLM call, a tool call,
        a retrieval step, none of which is one of the engine's own per-knot
        lifecycle transitions — has no such constraint: it can simply await
        each emitter directly, in order, and this is that path.

        Args:
            event: The status event to deliver.
            emitters: The emitters to notify. Defaults to
                :func:`pirn.tapestry.current_emitters` (the enclosing run's
                subscription) when ``None`` — pass an explicit empty list to
                opt out rather than relying on the default resolving to one.
            policy: How to react to an emitter raising. Defaults to
                :func:`pirn.tapestry.current_emitter_error_policy` when
                ``None``.
        """
        from pirn.tapestry import current_emitter_error_policy, current_emitters

        active_emitters = emitters if emitters is not None else current_emitters()
        active_policy = policy if policy is not None else current_emitter_error_policy()
        for emitter in active_emitters:
            try:
                await emitter.on_status(event)
            except Exception as exc:
                EmitterFanout.handle_emitter_error(emitter, "on_status", exc, active_policy)
