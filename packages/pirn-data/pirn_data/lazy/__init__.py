"""Tier-3 push-down / distributed engines (Ibis, Dask, Ray Data, Spark).

Import policy: each ``lazy/{engine}/`` subpackage imports its vendor
library at module top level (``import ibis``, ``import dask.dataframe``,
``import ray``), the same convention ``pirn_data.frames`` uses for the
Tier-2 native-frame engines — the engine is the subpackage's identity,
and the whole subpackage is opt-in via its own ``pirn-data[{engine}]``
extra (``ibis``, ``dask``, ``ray-data``), so the top-level import never
breaks an installation that didn't ask for it.

``lazy/spark/`` is the deliberate exception: every ``pyspark`` import
in that subpackage is deferred to inside ``process()`` (or a helper it
calls), because PySpark's JVM bootstrap cost is high enough that even
constructing an unrelated knot elsewhere in the process should not pay
for it. Value objects such as ``SparkDataFrame`` type their wrapped
frame as ``Any`` for the same reason — importing ``pyspark.sql`` just
to spell the type would defeat the point of lazy-importing it.

Modules outside the tier-engine subpackages (``lakehouse/``,
``validation/``, ``specialized/``) always lazy-import their vendor SDK,
since those modules are commonly reached, or support more than one
optional backend, regardless of whether that particular backend is
installed.

See ``docs/domains/data.md`` (“Tiered Architecture”) for the full tier
table and the extras each engine maps to.
"""
