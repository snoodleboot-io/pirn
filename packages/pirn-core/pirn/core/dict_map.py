"""``DictMap`` — wiring-time marker that fans a knot out over the entries of a dict."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class DictMap:
    """Wiring-time marker that fans a knot out over the entries of a dict.

    Wrap the same source knot in ``DictMap(source)`` on two separate input
    arguments of the receiving knot.  By declaration order, the first
    ``DictMap``-annotated argument receives the dict key and the second
    receives the corresponding value for each entry.  Iteration follows
    insertion order (Python 3.7+ dict semantics).  All per-entry invocations
    run concurrently.  The knot's overall output is ``list[T]``.

    ``DictMap`` is not a ``Knot`` subclass.  Like ``Map`` and ``ZipMap``, it is
    a plain Python marker object consumed at construction time by
    ``Knot.__init__`` and not present at execution time.

    Constraints:
        - Exactly two ``DictMap``-annotated inputs must appear on the same knot,
          both wrapping the same source knot.
        - The source knot must produce a ``dict`` at runtime.
        - Cannot be combined with ``Map`` or ``ZipMap`` on the same knot.
    """

    def __init__(self, source: Knot) -> None:
        self._source = source

    @property
    def source(self) -> Knot:
        return self._source
