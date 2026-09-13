"""``SpanStatus`` — terminal disposition of a :class:`Span`.

.. deprecated:: ADR agents-speaks-core WS4a
    Part of the deprecated Tracer/Span plane; scheduled for deletion after one
    release cycle. The replacement,
    :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
    reports outcome as core's own ``KnotState.SUCCEEDED``/``KnotState.FAILED``
    instead of a parallel enum.
"""

from __future__ import annotations

from enum import Enum


class SpanStatus(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Outcome of a span.

    .. deprecated:: ADR agents-speaks-core WS4a
        See the module docstring.

    Members
    -------
    UNSET:
        The span has not finished yet.
    OK:
        The wrapped operation completed successfully.
    ERROR:
        The wrapped operation raised or otherwise failed.
    """

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"
