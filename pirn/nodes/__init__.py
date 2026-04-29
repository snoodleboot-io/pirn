"""Phase 2 node taxonomy.

* ``Source`` — zero parents, produces values from outside.
* ``Sink`` — terminal consumer, output conventionally None.
* ``Aggregator`` — N parents → one combined value.
* ``Branch`` — one input → tagged output; downstream branches activate or skip.
* ``Gate`` — one input → pass through or skip via predicate.
* ``Map`` — wrapper that applies an inner knot to each element of a collection.
* ``Reduce`` — collects a Map's outputs into a single value.

(``Optional`` is a mixin, defined in ``pirn.core.knot``; not a node.)
"""

from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch import Branch, BranchOutput
from pirn.nodes.gate import Gate
from pirn.nodes.map_ import Map
from pirn.nodes.reduce_ import Reduce
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source

__all__ = [
    "Aggregator",
    "Branch",
    "BranchOutput",
    "Gate",
    "Map",
    "Reduce",
    "Sink",
    "Source",
]
