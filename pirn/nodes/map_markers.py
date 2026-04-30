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
    """Fan a knot out over an ordered collection (list or tuple).

    The annotated input receives one element per invocation.  All
    invocations run concurrently.  Output type is list[T].
    """

    def __init__(self, source: "Knot") -> None:
        self._source = source

    @property
    def source(self) -> "Knot":
        return self._source


class ZipMap:
    """Fan a knot out over multiple collections element-wise.

    All ZipMap-annotated inputs on the same knot are zipped together
    (shortest-collection semantics, matching Python's zip).  Output type
    is list[T].
    """

    def __init__(self, source: "Knot") -> None:
        self._source = source

    @property
    def source(self) -> "Knot":
        return self._source


class DictMap:
    """Fan a knot out over the entries of a dict.

    Both the key-receiving and value-receiving inputs must annotate the
    same source knot.  By insertion order, the first DictMap-annotated
    input receives the key and the second receives the value for each
    entry.  Output type is list[T].
    """

    def __init__(self, source: "Knot") -> None:
        self._source = source

    @property
    def source(self) -> "Knot":
        return self._source
