"""``Map`` — wiring-time marker that fans a knot out over an ordered collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class Map:
    """Wiring-time marker that fans a knot out over an ordered collection.

    Wrap a source knot in ``Map(source)`` when passing it as an input argument
    to declare that the receiving knot should be invoked once per element of the
    list or tuple produced by ``source``.  All per-element invocations run
    concurrently.  The knot's overall output is ``list[T]`` where ``T`` is the
    per-element return type.

    ``Map`` is not a ``Knot`` subclass.  It is a plain Python marker object
    consumed at construction time by ``Knot.__init__``, which replaces it with
    the unwrapped source knot and records the fan-out intent in
    ``_mutable_mapped_inputs``.  The marker is not present at execution time.

    Constraints:
        - The source knot must produce a ``list`` or ``tuple`` at runtime.
        - Only one ``Map``-annotated input per knot is allowed (use ``ZipMap``
          for parallel multi-collection fan-out).
        - Cannot be combined with ``ZipMap`` or ``DictMap`` on the same knot.
    """

    def __init__(self, source: Knot) -> None:
        self._source = source

    @property
    def source(self) -> Knot:
        return self._source
