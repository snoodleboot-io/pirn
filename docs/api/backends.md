# Backends

Storage backend protocols and all built-in implementations.

---

## Protocols

::: pirn.backends.base.tapestry_store.TapestryStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.base.run_history.RunHistory
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.base.data_store.DataStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.base.subscribable_store.SubscribableStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## In-memory (default)

::: pirn.backends.in_memory.in_memory_store.InMemoryStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.in_memory.in_memory_history.InMemoryHistory
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.in_memory.in_memory_data_store.InMemoryDataStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## SQLite (base install, stdlib `sqlite3`)

::: pirn.backends.sqlite.sqlite_store.SQLiteStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.sqlite.sqlite_history.SQLiteHistory
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Postgres (`pirn-core[postgres]`)

::: pirn.backends.postgres.postgres_store.PostgresStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.postgres.postgres_history.PostgresHistory
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## DuckDB (`pirn-core[duckdb]`)

::: pirn.backends.duckdb_history.DuckDBHistory
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## Local disk

::: pirn.backends.local_disk_data_store.LocalDiskDataStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## S3 (`pirn-core[s3]`)

::: pirn.backends.s3_data_store.S3DataStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

---

## ValKey (`pirn-core[valkey]`)

::: pirn.backends.valkey.valkey_store.ValKeyStore
    options:
      show_source: false
      members_order: source
      heading_level: 3

::: pirn.backends.valkey.valkey_data_store.ValKeyDataStore
    options:
      show_source: false
      members_order: source
      heading_level: 3
