"""``EmitterFanout`` — wires a run's emitters to its status/lineage/result streams.

Extracted out of ``Engine`` (a pure move, PIR-856): neither method reads or
writes any ``Engine`` instance state, so both are ``@staticmethod``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.engine._emitter_subscriber import _EmitterSubscriber

if TYPE_CHECKING:
    from pirn.core.run_context import RunContext

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
