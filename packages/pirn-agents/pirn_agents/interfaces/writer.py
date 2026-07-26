"""``Writer`` — shared interface for every state-writing knot.

The DIP seam behind the writer family. A writer persists some state and returns
a handle describing what was written. Today the memory umbrella is the sole
implementer family: its
:class:`~pirn_agents.memory.memory_writer_base.MemoryWriterBase` rebases onto
this abstraction, so all six memory writers (key/value, typed record, episode,
fact, procedure, sliding window) become ``Writer`` implementations through it.
Anchoring the family on a package-neutral base lets callers depend on the role
``Writer`` rather than a memory-specific base, and keeps the abstraction open to
future non-memory writers without an import inversion.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.core.knot.Knot` whose :meth:`process` raises
:class:`NotImplementedError`; each concrete writer overrides ``process`` with
its own persistence signature — exactly as it previously overrode
``Knot.process`` — so the rebase changes no observable behavior.

References:
    - :class:`pirn.core.knot.Knot`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class Writer(Knot):
    """Abstract base for knots that persist state and return a storage handle.

    Concrete writers subclass this and override :meth:`process` with their own
    keyword signature. The base itself is never placed in a graph directly; it
    exists so writers share one abstraction (DIP) and one substitutable contract
    (LSP): each ``process`` performs one or more writes and returns a handle
    describing what was written.
    """

    async def process(self, **kwargs: Any) -> Any:
        """Persist state and return a storage handle.

        Concrete subclasses override this with their own keyword parameters and
        return type. The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
