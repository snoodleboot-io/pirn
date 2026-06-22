"""Wiring-time markers for input-site distribution.

Place these on a knot's input arguments to instruct the engine to fan the
knot out over a collection at execution time.

    analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
    process_pair(a=ZipMap(knot_a), b=ZipMap(knot_b), _config=KnotConfig(id="pairs"))
    process_entry(key=DictMap(lookup), value=DictMap(lookup), _config=KnotConfig(id="entries"))

None of these are Knot subclasses.  They are plain Python objects consumed
at construction time by Knot.__init__ and replaced by their source knots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class MapTypeError(TypeError):
    """Raised when a mapped input receives a collection of the wrong type."""


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
