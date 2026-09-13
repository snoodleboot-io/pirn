"""Wiring-time markers for input-site distribution.

Place these on a knot's input arguments to instruct the engine to fan the
knot out over a collection at execution time.

    analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
    process_pair(a=ZipMap(knot_a), b=ZipMap(knot_b), _config=KnotConfig(id="pairs"))
    process_entry(key=DictMap(lookup), value=DictMap(lookup), _config=KnotConfig(id="entries"))

None of these are Knot subclasses.  They are plain Python objects consumed
at construction time by Knot.__init__ and replaced by their source knots.

Compat module: the marker classes live in ``pirn.core`` (one per file) so
that ``pirn.core.knot`` — which must construct and type-check them — does
not import from ``pirn.nodes``, inverting the core/nodes layering.  This
module re-exports them from their canonical location for existing
importers; new code should prefer importing directly from ``pirn.core``.
"""

from __future__ import annotations

from pirn.core.dict_map import DictMap
from pirn.core.map import Map
from pirn.core.map_type_error import MapTypeError
from pirn.core.zip_map import ZipMap

__all__ = ["DictMap", "Map", "MapTypeError", "ZipMap"]
