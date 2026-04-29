# Schema migrations

pirn manages its own database schema for the `SQLiteStore`, `SQLiteHistory`,
`PostgresStore`, and `PostgresHistory` backends. This document explains how
the schema is versioned and how to add a migration when the schema changes.

## Version tracking

Each backend maintains a `pirn_schema_version` table:

```sql
CREATE TABLE IF NOT EXISTS pirn_schema_version (
    component TEXT PRIMARY KEY,
    version   INTEGER NOT NULL
);
```

There are two components tracked independently:

| component | covers |
|-----------|--------|
| `store`   | the `knots` table |
| `history` | the `runs`, `lineage`, and `lineage_inputs` tables |

The current version for each component is defined as a module-level constant:

```python
_STORE_SCHEMA_VERSION   = 1   # pirn/backends/postgres.py (and sqlite.py)
_HISTORY_SCHEMA_VERSION = 1
```

## How init works

On first use, `_ensure_init()` (async in Postgres, sync in SQLite):

1. Creates `pirn_schema_version` if it does not exist.
2. Runs the component's DDL (`CREATE TABLE IF NOT EXISTS …`).
3. Calls `_apply_migrations(conn, component, target)` which steps through any
   pending migration functions and upserts the version row.

This means a fresh database goes from version 0 to `target` in one shot, and
an existing database is advanced one step at a time.

## Adding a migration

Say you need to add a `tags JSONB` column to the `lineage` table (schema
version 1 → 2):

### 1. Write the migration function

**Postgres** (`pirn/backends/postgres.py`):

```python
async def _migrate_history_1_to_2(conn: Any) -> None:
    await conn.execute(
        "ALTER TABLE lineage ADD COLUMN IF NOT EXISTS tags JSONB"
    )
```

**SQLite** (`pirn/backends/sqlite.py`):

```python
def _migrate_history_1_to_2(conn: Any) -> None:
    conn.execute("ALTER TABLE lineage ADD COLUMN tags TEXT")
```

SQLite does not support `IF NOT EXISTS` on `ALTER TABLE`, so the migration
must be idempotent by other means (e.g. catching `OperationalError`).

### 2. Bump the version constant

```python
_HISTORY_SCHEMA_VERSION = 2
```

### 3. Register the migration in `_apply_migrations`

**Postgres** — in `PostgresStore._apply_migrations`:

```python
for v in range(current, target):
    if v == 1:
        await _migrate_history_1_to_2(conn)
```

**SQLite** — in `_apply_sqlite_migrations`:

```python
for v in range(current, target):
    if v == 1:
        _migrate_history_1_to_2(conn)
```

### 4. Update the DDL

Add `tags JSONB` (or `TEXT` for SQLite) to the `CREATE TABLE` DDL so fresh
databases get the column without running the migration.

### 5. Write a test

Add a test that starts from a v1 schema, runs `_apply_migrations` with
`target=2`, and asserts the column exists. This guards against the migration
being skipped or erroring silently.

## Policy

- Migrations are **additive only** for as long as possible (add columns,
  add indexes, add tables). Destructive changes (drop column, rename column)
  require a multi-step approach: add the new column in vN, backfill in vN+1,
  drop the old column in vN+2.
- The `pirn_schema_version` table is never dropped by pirn itself. If you
  need to reset a development database, drop all pirn tables including
  `pirn_schema_version`.
- Migration functions are async in Postgres (to match asyncpg) and sync in
  SQLite (standard library `sqlite3`).
- DuckDB uses no migration table — it is a read-optimised analytics backend
  whose schema is expected to be recreated from scratch when it changes.

## Testing migrations locally

```bash
# Bring up Postgres
source scripts/test-env-up.sh

# Simulate an old schema by inserting a stale version row, then run init
psql $PIRN_TEST_POSTGRES_URL -c \
  "INSERT INTO pirn_schema_version VALUES ('history', 1) ON CONFLICT DO NOTHING"

# Run the suite — _ensure_init should advance to the current version
python -m pytest -q --real -m needs_postgres
```
