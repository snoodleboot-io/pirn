# Standalone Functions Review

Generated: 2026-04-29  
Purpose: Audit of all module-level functions in `pirn/`. Each group has a recommended disposition and a column for owner input.

---

## Legend

| Disposition | Meaning |
|-------------|---------|
| ✅ Keep as-is | Legitimately standalone; no class home makes sense |
| 🔄 Move to class | Has a natural owner class; should become a method |
| 🗑️ Remove | Dead code or better deleted |
| ❓ Discuss | Unclear; needs input |

---

## Group 1 — Backend I/O Helpers

These exist solely to be passed to `asyncio.to_thread` and cannot be lambdas.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [backends/disk.py](../pirn/backends/disk.py) | `_disk_write` | Writes bytes to a path (creates parent dirs) | ✅ Keep as-is | |
| [backends/disk.py](../pirn/backends/disk.py) | `_disk_read` | Reads bytes from a path, raises KeyError if missing | ✅ Keep as-is | |
| [backends/disk.py](../pirn/backends/disk.py) | `_disk_unlink` | Deletes a file if it exists | ✅ Keep as-is | |

---

## Group 2 — Cryptographic Primitives

Pure functions on bytes; no state. Used by `LocalDiskDataStore` and signing key setup.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [backends/_signing.py](../pirn/backends/_signing.py) | `sign` | HMAC-signs a payload | ✅ Keep as-is | |
| [backends/_signing.py](../pirn/backends/_signing.py) | `verify` | Verifies and strips HMAC signature | ✅ Keep as-is | |
| [backends/signing_key.py](../pirn/backends/signing_key.py) | `signing_key_from_env` | Reads + base64-decodes signing key from env var | ✅ Keep as-is | |

---

## Group 3 — Database / Migration Utilities

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [backends/sqlite/_migrations.py](../pirn/backends/sqlite/_migrations.py) | `apply_migrations` | Runs versioned DDL migrations against a SQLite connection | ✅ Keep as-is | |
| [backends/postgres/_lazy_pool.py](../pirn/backends/postgres/_lazy_pool.py) | `_sanitize_dsn` | Redacts password from a DSN string for safe logging | 🔄 Move to class | Could be a static method on the Postgres backend class |

---

## Group 4 — Graph / Validation Traversal

Stateless recursive graph walkers. No class owns a graph traversal by itself.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [engine/shed/shed.py](../pirn/engine/shed/shed.py) | `_visit_dfs` | DFS visitor used by `_detect_cycle` | ✅ Keep as-is | |
| [engine/shed/shed.py](../pirn/engine/shed/shed.py) | `_detect_cycle` | Detects cycles in a shed's adjacency list | ✅ Keep as-is | |
| [check/validator.py](../pirn/check/validator.py) | `_dfs` | DFS used by `validate_tapestry` | ✅ Keep as-is | |
| [check/validator.py](../pirn/check/validator.py) | `validate_tapestry` | Validates a Tapestry for cycles and orphans | ✅ Keep as-is | |

---

## Group 5 — Hashing

Pure stateless functions. Would be a strange fit as class methods.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [core/hashing.py](../pirn/core/hashing.py) | `content_hash` | Stable sha256 hex of any Python value | ✅ Keep as-is | |
| [core/hashing.py](../pirn/core/hashing.py) | `_canonicalise` | Recursively converts a value to a JSON-serialisable canonical form | ✅ Keep as-is | |

---

## Group 6 — `@knot` Decorator Machinery

Factory pipeline for the `@knot` decorator. These compose in sequence; splitting to a class would obscure the pipeline.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [core/knot_factory.py](../pirn/core/knot_factory.py) | `knot` | Public decorator entrypoint | ✅ Keep as-is | |
| [core/knot_factory.py](../pirn/core/knot_factory.py) | `_make_knot_factory` | Builds a `KnotFactory` from a callable | ✅ Keep as-is | |
| [core/knot_factory.py](../pirn/core/knot_factory.py) | `_make_async_process` | Generates a `process` method body for async functions | ✅ Keep as-is | |
| [core/knot_factory.py](../pirn/core/knot_factory.py) | `_make_sync_process` | Generates a `process` method body for sync functions | ✅ Keep as-is | |
| [core/knot_factory.py](../pirn/core/knot_factory.py) | `_pending_record` | Builds a placeholder `ExceptionRecord` before a run context exists | ❓ Discuss | Lives in factory but is used by `Knot.__call__`; may belong in `exception_manager` or `err.py` |

---

## Group 7 — Distributed Dispatcher Bridges

Must be importable at module scope by external workers (Celery, Dask, Ray) or passed to executor APIs. Cannot be instance methods.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [engine/dispatchers/celery_dispatcher.py](../pirn/engine/dispatchers/celery_dispatcher.py) | `_run_knot_sync` | Celery worker task body; runs a knot synchronously | ✅ Keep as-is | |
| [engine/dispatchers/celery_dispatcher.py](../pirn/engine/dispatchers/celery_dispatcher.py) | `register_celery_worker_task` | Registers `_run_knot_sync` with a Celery app | ✅ Keep as-is | |
| [engine/dispatchers/dask_dispatcher.py](../pirn/engine/dispatchers/dask_dispatcher.py) | `_dask_run_knot` | Dask task body; must be picklable (top-level only) | ✅ Keep as-is | |
| [engine/dispatchers/ray_dispatcher.py](../pirn/engine/dispatchers/ray_dispatcher.py) | `_ray_run_knot` | Ray remote task body; must be top-level for `@ray.remote` | ✅ Keep as-is | |
| [engine/dispatchers/thread_dispatcher.py](../pirn/engine/dispatchers/thread_dispatcher.py) | `_run_in_thread` | Passed to `executor.submit`; bridges async knot into thread pool | ✅ Keep as-is | |

---

## Group 8 — Emitter / Trigger Infrastructure

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [engine/_emitter_subscriber.py](../pirn/engine/_emitter_subscriber.py) | `_emit_event` | Coroutine body called by `_EmitterSubscriber.__call__` | 🔄 Move to class | Natural fit as a private method on `_EmitterSubscriber` |
| [managers/redact.py](../pirn/managers/redact.py) | `redact_common_secrets` | Scrubs known secret patterns from exception message strings | ✅ Keep as-is | |
| [emitters/otel.py](../pirn/emitters/otel.py) | `_otel_status_error` | Builds an OTel StatusCode.ERROR object | 🔄 Move to class | Could be a static/class method on `OpenTelemetryEmitter` |
| [emitters/otel.py](../pirn/emitters/otel.py) | `_otel_status_unset` | Builds an OTel StatusCode.UNSET object | 🔄 Move to class | Same as above |
| [emitters/webhook.py](../pirn/emitters/webhook.py) | `_check_url_for_ssrf` | Validates a URL is not an internal/private address | 🔄 Move to class | Natural static method on `WebhookEmitter` |
| [emitters/webhook.py](../pirn/emitters/webhook.py) | `_check_url_scheme` | Validates URL scheme is `https` (or allowed) | 🔄 Move to class | Same as above |

---

## Group 9 — Trigger Default Builders

Default callable passed as `request_builder` when none is provided. Needs to be referenceable as a default argument.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [triggers/http.py](../pirn/triggers/http.py) | `_default_request_builder` | Treats JSON body as `RunRequest` parameters dict | ❓ Discuss | Default arg on `WebhookTrigger.__init__`; could be a static method but loses default-arg ergonomics |
| [triggers/kafka.py](../pirn/triggers/kafka.py) | `_default_request_builder` | Deserialises Kafka message bytes to `RunRequest` | ❓ Discuss | Same pattern |
| [triggers/valkey.py](../pirn/triggers/valkey.py) | `_default_request_builder` | Deserialises ValKey message to `RunRequest` | ❓ Discuss | Same pattern |
| [streaming/kafka.py](../pirn/streaming/kafka.py) | `_default_decoder` | Decodes Kafka message bytes to Python value | ❓ Discuss | Same pattern |

---

## Group 10 — Map Node Helpers

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [nodes/map_.py](../pirn/nodes/map_.py) | `_run_one` | Constructs and runs one inner knot for a single element | ✅ Keep as-is | |
| [nodes/map_.py](../pirn/nodes/map_.py) | `_is_knot_factory` | Returns True if obj is a Knot subclass or KnotFactory | 🔄 Move to class | Could be a static method on `Map` |
| [nodes/map_.py](../pirn/nodes/map_.py) | `_construct_inner` | Constructs an inner Knot from a class or factory | 🔄 Move to class | Could be a static method on `Map` |

---

## Group 11 — Public API Entry Points

Correct as module-level; these are the library's callable surface.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [check/main.py](../pirn/check/main.py) | `main` | CLI entry point for `tapestry-check` | ✅ Keep as-is | |
| [check/_loader.py](../pirn/check/_loader.py) | `_load_factory` | Dynamically imports a tapestry factory for CLI use | ✅ Keep as-is | |
| [tapestry.py](../pirn/tapestry.py) | `current_tapestry` | Returns the active `Tapestry` context var value | ✅ Keep as-is | |
| [replay.py](../pirn/replay.py) | `replay_run` | Replays a previous `RunResult` against a tapestry | ✅ Keep as-is | |
| [replay.py](../pirn/replay.py) | `compare_runs` | Diffs two `RunResult`s by knot output hashes | ✅ Keep as-is | |
| [streaming/base.py](../pirn/streaming/base.py) | `run_stream` | Async loop: pulls from a `StreamingSource`, runs a tapestry per item | ✅ Keep as-is | |
| [triggers/base.py](../pirn/triggers/base.py) | `run_forever` | Async loop: pulls from a `Trigger`, runs a tapestry per request | ✅ Keep as-is | |

---

## Group 12 — Visualisation Helpers

Stateless rendering pipeline. No persistent state; no natural class.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [viz/html.py](../pirn/viz/html.py) | `html_for_run` | Public entry: renders a `RunResult` to a standalone HTML doc | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_get_depth` | Recursive longest-path depth calculator | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_layer_nodes` | Groups nodes into depth layers | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_assign_coordinates` | Assigns (x, y) pixel coords to each node | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_render_summary` | Renders the run summary header HTML | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_render_svg` | Renders the SVG graph body | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_short` | Strips module prefix from a qualified class name | ✅ Keep as-is | |
| [viz/html.py](../pirn/viz/html.py) | `_truncate` | Truncates a string to n chars with ellipsis | ✅ Keep as-is | |
| [viz/mermaid.py](../pirn/viz/mermaid.py) | `mermaid_for_tapestry` | Public entry: renders a Tapestry to a Mermaid graph string | ✅ Keep as-is | |
| [viz/mermaid.py](../pirn/viz/mermaid.py) | `mermaid_for_run` | Public entry: renders a RunResult to a Mermaid graph with outcomes | ✅ Keep as-is | |
| [viz/mermaid.py](../pirn/viz/mermaid.py) | `_safe_node_id` | Sanitises a knot id to a valid Mermaid node identifier | ✅ Keep as-is | |
| [viz/mermaid.py](../pirn/viz/mermaid.py) | `_node_label` | Builds the display label for a node | ✅ Keep as-is | |
| [viz/mermaid.py](../pirn/viz/mermaid.py) | `_short_class` | Strips module prefix from class name (mermaid variant) | ✅ Keep as-is | |

---

## Group 13 — YAML Loader Pipeline

Internal steps of the `load_pipeline` function. No class owns the loading process.

| File | Function | What it does | Recommended | Owner Input |
|------|----------|-------------|-------------|-------------|
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `load_pipeline` | Public entry: parses YAML and populates a Tapestry | ✅ Keep as-is | |
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `_topo_order_specs` | Topologically sorts node specs using Kahn's algorithm | ✅ Keep as-is | |
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `_build_node` | Constructs a single Knot from its spec | ✅ Keep as-is | |
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `_resolve_callable` | Resolves a string ref → callable via known/registry/import | ✅ Keep as-is | |
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `_resolve_type` | Resolves a type string (e.g. `"list[dict]"`) to a Python type | ✅ Keep as-is | |
| [yaml_loader/loader.py](../pirn/yaml_loader/loader.py) | `_import_dotted` | Imports a dotted path and returns the named attribute | ✅ Keep as-is | |

---

## Summary

| Disposition | Count |
|-------------|-------|
| ✅ Keep as-is | 44 |
| 🔄 Move to class | 9 |
| ❓ Discuss | 5 |
| 🗑️ Remove | 0 |

### Move to class — shortlist
- `_sanitize_dsn` → static method on Postgres backend class
- `_emit_event` → private method on `_EmitterSubscriber`
- `_otel_status_error`, `_otel_status_unset` → static methods on `OpenTelemetryEmitter`
- `_check_url_for_ssrf`, `_check_url_scheme` → static methods on `WebhookEmitter`
- `_is_knot_factory`, `_construct_inner` → static methods on `Map`

### Discuss — shortlist
- `_pending_record` in `knot_factory.py` — belongs closer to error/exception machinery
- Three `_default_request_builder` functions and `_default_decoder` — default arg ergonomics vs. static method clarity
