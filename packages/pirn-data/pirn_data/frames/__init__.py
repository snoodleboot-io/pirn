"""Tier-2 native-frame engines (Polars, DataFusion, DuckDB, pandas, PyArrow).

Import policy: each ``frames/{engine}/`` subpackage imports its vendor
library at module top level (``import polars``, ``import duckdb``, …).
The engine *is* the subpackage's identity — a module in
``frames/polars/`` is meaningless without Polars — and the whole
subpackage is opt-in via its own ``pirn-data[{engine}]`` extra, so a
top-level import never breaks an installation that didn't ask for that
engine. This differs from ``lakehouse/``, ``validation/``, and
``specialized/``, whose modules lazy-import their vendor SDK inside
``process()`` (or a helper called from it) because a single module in
those subpackages often supports more than one optional backend, or is
reached from a code path that should not require the dependency at
all (e.g. constructing a knot before it ever runs).

The one exception among the tier engines is ``lazy/spark/`` (see
``pirn_data.lazy``): PySpark's JVM bootstrap cost is high enough that
even that subpackage lazy-imports, trading the "engine at module top"
convention for faster import of everything that doesn't touch Spark.

See ``docs/domains/data.md`` (“Tiered Architecture”) for the full tier
table and the extras each engine maps to.
"""
