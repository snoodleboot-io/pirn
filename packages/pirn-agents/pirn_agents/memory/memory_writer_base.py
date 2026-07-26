"""``MemoryWriterBase`` — shared interface for every memory-writing knot.

The DIP seam behind the memory umbrella's writers. Every concrete writer
persists something (a key/value entry, a typed record, an episode, a fact, a
procedure, or a sliding window) into a
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` and returns a
storage handle. Consolidating them onto one base lets callers depend on the
abstraction ``MemoryWriterBase`` rather than each concrete writer, and gives the
future shared ``interfaces.Writer`` a single memory-facing anchor to rebase onto.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.core.knot.Knot` whose :meth:`process` raises
:class:`NotImplementedError`; each concrete writer overrides ``process`` with
its own persistence signature — exactly as it previously overrode
``Knot.process`` — so the collapse changes no observable behavior.

References:
    - :class:`pirn_agents.memory.stores.memory_store.MemoryStore`
    - :class:`pirn.core.knot.Knot`
"""

from __future__ import annotations

from typing import Any

from pirn_agents.interfaces.writer import Writer


class MemoryWriterBase(Writer):
    """Abstract base for knots that persist state into a ``MemoryStore``.

    Concrete writers subclass this and override :meth:`process` with their own
    keyword signature. The base itself is never placed in a graph directly; it
    exists so writers share one abstraction (DIP) and one substitutable
    contract (LSP): each ``process`` awaits one or more ``store`` writes and
    returns a storage handle describing what was written.
    """

    async def process(self, **kwargs: Any) -> Any:
        """Persist state into a ``MemoryStore`` and return a storage handle.

        Concrete subclasses override this with their own keyword parameters and
        return type. The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
