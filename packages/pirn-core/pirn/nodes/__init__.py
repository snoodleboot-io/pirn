"""Phase 2 node taxonomy.

* ``Source`` — zero parents, produces values from outside.
* ``Sink`` — terminal consumer, output conventionally None.
* ``Aggregator`` — N parents → one combined value.
* ``Branch`` — one input → tagged output; downstream branches activate or skip.
* ``Gate`` — one input → pass through or skip via predicate, or via a ``Check``.
* ``Check`` — the predicate half of a ``Gate``: any parents → ``bool``.
* ``Map`` — wrapper that applies an inner knot to each element of a collection.
* ``Reduce`` — collects a Map's outputs into a single value.
* ``SubTapestry`` — base class for knots whose body is a complete inner tapestry pipeline.
* ``LoopSubTapestry`` — SubTapestry for iterative patterns; subclasses implement ``step``/``fold``.

(``Optional`` is a mixin, defined in ``pirn.core.knot``; not a node.)
"""
