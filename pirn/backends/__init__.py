"""Backend implementations for pirn.

Interface base classes live in ``pirn.backends.base``.
Implementations:
  - ``pirn.backends.in_memory`` — in-memory (default, single-process)
  - ``pirn.backends.sqlite`` — SQLite (durable, single-host)
  - ``pirn.backends.postgres`` — PostgreSQL via asyncpg
  - ``pirn.backends.valkey`` — ValKey/Redis
  - ``pirn.backends.duckdb`` — DuckDB (analytics history)
  - ``pirn.backends.disk`` — local disk data store
  - ``pirn.backends.s3`` — S3 data store
"""
