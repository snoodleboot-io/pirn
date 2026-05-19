# Subscribable stores

`InMemoryStore`, `PostgresStore`, and `ValKeyStore` implement the optional
`SubscribableStore` protocol, which lets other components react to knot
registrations in real time.

## API

```python
token = store.subscribe(callback)   # returns an opaque token
store.unsubscribe(token)            # stops the callback
```

The callback receives the live `Knot` object every time a new knot is
registered into the store.

## How each backend delivers notifications

### PostgresStore

Uses Postgres `LISTEN`/`NOTIFY`. After each `INSERT` in `aregister`, the
store executes `NOTIFY pirn_knots, <knot_id>`. A background asyncio task
holds a dedicated connection in `LISTEN` mode and calls registered callbacks
when notifications arrive.

### ValKeyStore

Uses ValKey pub/sub. After each write in `aregister`, the store publishes the
knot id to the `pirn:tapestry:registrations` channel. A background task holds
a separate pub/sub client and dispatches to callbacks on each message.

## Same-process limitation

**Callbacks only fire for knots registered by the same process.**

Both implementations look up the notified knot id in `self._live` — the
in-process dict of live `Knot` objects. A knot registered by another process
would not be in that dict, so the callback is silently skipped.

This is intentional for Phase 3. Cross-process delivery would require
deserialising a `Knot` from the database row, which is not supported because:

1. `Knot` objects hold callable references (the user's function) that cannot
   be serialised across process boundaries without a shared import path and
   protocol.
2. The typical use case for `subscribe` is mid-run extension within a single
   process (e.g. a dynamic loader that registers new knots as config arrives).
   Cross-process extension is better handled by restarting the worker and
   having it re-read the tapestry definition.

## What cross-process delivery would require

If you need callbacks to fire for knots registered by other processes:

1. Store enough metadata in the database row to reconstruct a minimal `Knot`
   proxy (class name, config dict, parent ids).
2. Agree on a shared import path so the receiving process can import the same
   knot class and instantiate it from config.
3. Handle the case where the receiving process does not have the knot class
   available (e.g. plugins not installed).

This is out of scope for Phase 3 but the `SubscribableStore` protocol is
designed to accommodate it in a future version.

## SQLiteStore

`SQLiteStore` does not implement `SubscribableStore`. SQLite's locking model
makes reliable cross-connection notification impractical. For local
single-process use `InMemoryStore`, which implements `SubscribableStore` and
delivers callbacks synchronously within the same process.
