"""``ZipMap`` — wiring-time marker that fans a knot out over multiple collections element-wise."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class ZipMap:
    """Wiring-time marker that fans a knot out over multiple collections element-wise.

    Wrap each of the parallel source knots in ``ZipMap(source)`` when passing
    them as input arguments.  All ``ZipMap``-annotated inputs on the same knot
    are zipped together — for each index ``i``, one invocation is created that
    receives ``collection_a[i]``, ``collection_b[i]``, and so on.  Semantics
    match Python's built-in ``zip`` (shortest-collection truncation).  All
    per-element invocations run concurrently.  The knot's overall output is
    ``list[T]``.

    ``ZipMap`` is not a ``Knot`` subclass.  Like ``Map``, it is a plain Python
    marker object consumed at construction time by ``Knot.__init__`` and not
    present at execution time.

    Constraints:
        - Every ``ZipMap``-annotated input on the same knot must wrap a
          different source knot.
        - All zipped source knots must produce sequences of the same length
          (or the shortest one determines the number of invocations).
        - Cannot be combined with ``Map`` or ``DictMap`` on the same knot.
    """

    def __init__(self, source: Knot) -> None:
        self._source = source

    @property
    def source(self) -> Knot:
        return self._source
