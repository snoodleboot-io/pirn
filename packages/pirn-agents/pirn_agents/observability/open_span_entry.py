"""``OpenSpanEntry`` — one span's slot on the tracer's task-local nesting stack."""

from __future__ import annotations


class OpenSpanEntry:
    """A span's presence on the nesting stack, closable from any context.

    The nesting stack lives in a :class:`~contextvars.ContextVar` holding an
    immutable tuple, so a push in one task is invisible to its siblings
    (PIR-788). That isolation is exactly what makes a *close* hard: rebuilding
    the tuple only affects the context doing the rebuilding, so a span finished
    on a ``ThreadDispatcher`` worker left its entry stranded in the opener's
    context forever, mis-parenting every span the opener started afterwards.

    Splitting the two operations across the two mechanisms resolves it. The
    tuple write stays context-local and keeps sibling isolation intact, while
    closing flips a flag on this shared, mutable object — and every context that
    copied the tuple copied the *reference*, so all of them observe the close at
    once, whichever one performs it. Readers skip closed entries, and the next
    push prunes them, so a closed entry is never a parent and never accumulates.
    """

    def __init__(self, tracer_key: str, span_id: str) -> None:
        """Open an entry for ``span_id`` belonging to the tracer ``tracer_key``.

        Args:
            tracer_key: Identifies the owning tracer, so two tracers alive in
                one task keep separate trees.
            span_id: The span this entry stands for.
        """
        self._tracer_key = tracer_key
        self._span_id = span_id
        self._closed = False

    @property
    def tracer_key(self) -> str:
        """The owning tracer's key."""
        return self._tracer_key

    @property
    def span_id(self) -> str:
        """The id of the span this entry stands for."""
        return self._span_id

    @property
    def closed(self) -> bool:
        """Whether the span has finished; closed entries never parent anything."""
        return self._closed

    def close(self) -> None:
        """Mark the span finished, in every context holding this entry.

        Idempotent, matching ``Span.finish``: a double close is a no-op rather
        than an error.
        """
        self._closed = True
