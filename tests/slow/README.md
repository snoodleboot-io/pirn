# Slow tests

Reserved for tests that are too slow to run on every push.

Phase 2 has no slow tests yet. Phase 3 will add tests covering:

* Networked backends (SQLite, Postgres, ValKey via valkey-glide) where
  the cost of spinning up a real or containerised server is non-trivial.
* Property-based tests with large search spaces.
* Soak tests for `ThreadDispatcher` and the future `DaskDispatcher` /
  `RayDispatcher`.

Run separately with:

```
pytest tests/slow
```
