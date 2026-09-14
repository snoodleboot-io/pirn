"""Tier-3 push-down / distributed engines (Ibis, Dask, Ray Data, Spark).

Import policy: no module in this subpackage imports its engine at module
scope, so ``import pirn_data`` (whose registry fill imports every module) loads
no optional engine. Each module imports the engine only under
``if TYPE_CHECKING:`` for its annotations. Every knot declares the engine in
``Knot._annotation_imports`` (``AnnotationImport(module, extra=, package="pirn-data")``),
which ``Knot`` resolves through ``OptionalDependency.require`` when the knot is
first constructed: annotations that name engine types validate exactly as an
eager import would, and a missing engine raises the ``pirn-data[{engine}]``
install hint at construction. Code that uses the engine at run time imports it
inside the method (a plain ``import polars as pl``, fully typed), which is only
reachable from a constructed knot whose engine has already resolved.

``lazy/spark/`` goes further: it declares no annotation imports and types its
wrapped frame as ``Any``, so even constructing a Spark knot does not pay
PySpark's JVM bootstrap; ``pyspark`` is imported only inside ``process()``.

See ``docs/domains/data.md`` (“Tiered Architecture”) for the full tier
table and the extras each engine maps to.
"""
