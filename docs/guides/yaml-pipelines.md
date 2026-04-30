# YAML Pipelines

pirn pipelines can be declared entirely in YAML and loaded at runtime with `load_pipeline()`. The YAML loader is a strict-by-default tool that translates a pipeline definition file into a live `Tapestry`.

---

## Entry point

```python
from pirn import load_pipeline, RunRequest

tapestry = load_pipeline(
    yaml_text,                              # str or Path
    known_callables={"my_fn": my_fn},      # name → callable
    tapestry=existing_tapestry,            # optional; new Tapestry() if omitted
)

result = await tapestry.run(RunRequest(parameters={"x": 5}))
```

`load_pipeline` returns a fully-constructed `Tapestry` with all knots registered. You can run it immediately or attach emitters before running.

---

## Top-level fields

```yaml
name: my_pipeline               # optional label
allow_callable_refs: false      # strict mode (default); set true for loose mode
nodes:
  - ...
```

### `allow_callable_refs`

Controls how callable references in node specs are resolved.

**`false` (strict, default):** every callable reference must be a key in `known_callables`. The loader resolves by dictionary lookup; no imports are performed. This is safe for user-provided YAML (database-stored pipelines, API payloads) because no arbitrary code can be imported.

**`true` (loose):** if a callable reference is not in `known_callables`, the loader treats it as a dotted import path and calls `importlib.import_module`. Example: `"myapp.transforms.score"` imports `myapp.transforms` and gets `score`.

!!! warning "Security: loose mode"
    Setting `allow_callable_refs: true` enables dynamic Python imports from YAML content. Only use this with YAML authored by the same trust boundary as the runtime — never with user-supplied YAML. An attacker who can write the YAML can execute arbitrary code.

---

## Node types

Every node spec shares a common set of fields plus type-specific fields.

### Common fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | required | Unique id within the pipeline |
| `type` | str | required | Node type (see below) |
| `validate_io` | bool | `true` | Enable Pydantic input/output validation |
| `error_policy` | str | `"skip_if_parent_failed"` | `"skip_if_parent_failed"`, `"receive_errors"`, `"require_all_parents"` |
| `description` | str | `""` | Human-readable description |
| `tags` | list[str] | `[]` | Arbitrary tags |

### `parameter`

An external input binding.

```yaml
- id: user_id
  type: parameter
  type_: str             # Python built-in or dotted path
  has_default: false     # optional
  default: null          # value if has_default is true
```

`type_` can be any Python type name resolvable from the standard library or via dotted import (e.g. `"int"`, `"str"`, `"datetime.datetime"`, `"myapp.models.User"`).

### `knot`

A typed async processing node.

```yaml
- id: enrich_user
  type: knot
  callable: enrich_user       # name in known_callables, or dotted path in loose mode
  parents:
    user_id: user_id          # {process_param_name: parent_node_id}
  config:
    timeout: 30               # static config values (not from parents)
  error_policy: require_all_parents
```

The `parents` dict maps this node's `process()` parameter names to other node ids. The `config` dict maps `process()` parameter names to constant values.

### `source`

A zero-parent producer (file read, DB query, fetch, etc.).

```yaml
- id: fetch_users
  type: source
  callable: FetchUsersSource
```

### `sink`

A terminal consumer with a `None` return.

```yaml
- id: write_results
  type: sink
  callable: WriteResultsSink
  parents:
    data: enrich_user
```

### `branch`

Routes one input to one of several named output paths. Non-selected paths become `Skipped`.

```yaml
- id: route_message
  type: branch
  input: classify_message     # node_id of the input to branch on
  selector: route_selector    # callable ref: (value) -> str branch name
  branches:
    - tool_call
    - response
    - error
```

Consume branch outputs in downstream nodes using `parents: {input: route_message}`. The branch node's output for each path is accessed by downstream nodes — only one path will produce `Ok`, the rest produce `Skipped`.

### `gate`

Passes through or skips based on a predicate.

```yaml
- id: quality_gate
  type: gate
  input: score_content        # node_id of the value to test
  predicate: is_high_quality  # callable ref: (value) -> bool
```

If the predicate returns `False`, downstream knots are skipped.

### `map`

Applies an inner knot to each element of a collection.

```yaml
- id: process_items
  type: map
  over: fetch_item_ids        # node_id producing a list
  each: process_single_item  # callable ref applied per element
  bind: item_id              # parameter name the element is bound to
  shared:                    # optional static values shared across all calls
    config_key: config_value
```

### `reduce`

Folds a list into a single value.

```yaml
- id: total_score
  type: reduce
  of: score_items             # node_id producing a list
  combine: sum                # callable ref: (list) -> value or (a, b) -> value
  initial: 0                  # optional initial value (pairwise reduce only)
```

### `aggregator`

Combines multiple parents via a merge function.

```yaml
- id: merged_results
  type: aggregator
  parents:
    left: process_left
    right: process_right
  combine: merge_dicts        # callable ref: (dict_of_results) -> value
```

---

## `known_callables`

A `Mapping[str, Any]` passed to `load_pipeline`. Values can be:

- Plain callables (sync or async functions)
- `KnotFactory` instances (from `@knot` decorator)
- `Knot` subclasses

The loader's `_resolve_callable` checks `known_callables` first. In strict mode, if a name is not found, `ValueError` is raised. In loose mode, the loader falls back to a dotted import.

### Auto-discovery with `fill_registry`

For `Knot` subclasses, use `sweet_tea`'s `fill_registry` at your application entry point. It recursively scans the package and registers every `Knot` subclass it finds — no manual dict required:

```python
# main.py (or wherever your app starts)
from sweet_tea.registry import Registry

Registry.fill_registry(module="myapp")   # scan your entire package

tapestry = load_pipeline(yaml_text)      # no known_callables needed
```

The YAML loader checks `KnotRegistry` automatically after `known_callables`, so any class registered via `fill_registry` is resolved by name.

For `@knot`-decorated functions (which produce factories, not importable classes), register them explicitly:

```python
from pirn.yaml_loader.knot_registry import KnotRegistry
from myapp.knots import score_text, route_selector

KnotRegistry.register("score_text", score_text)
KnotRegistry.register("route_selector", route_selector)
```

`known_callables` remains supported as a per-call override with the highest priority — useful in tests or when the same callable has multiple pipeline-specific aliases.

---

## Topological ordering

The loader uses Kahn's algorithm on the YAML specs before constructing any Python objects. This ensures each spec is built after all its referenced parents. The algorithm uses sorted ready-queues for determinism — identical to `Shed.topological_order()` in the engine.

If a cycle is detected in the YAML spec graph, `ValueError` is raised before any Python objects are created.

---

## Full example

```yaml
name: user_enrichment
allow_callable_refs: false

nodes:
  - id: user_id
    type: parameter
    type_: str

  - id: fetch_user
    type: knot
    callable: fetch_user
    parents:
      user_id: user_id
    error_policy: require_all_parents

  - id: score_engagement
    type: knot
    callable: score_engagement
    parents:
      user: fetch_user
    config:
      model_version: "v2"

  - id: is_high_value
    type: gate
    input: score_engagement
    predicate: high_value_predicate

  - id: enrich
    type: knot
    callable: enrich_premium_user
    parents:
      user: fetch_user
      score: score_engagement

  - id: store_result
    type: sink
    callable: StoreResultSink
    parents:
      enriched_user: enrich
```

```python
tapestry = load_pipeline(yaml_text, known_callables={
    "fetch_user": fetch_user,
    "score_engagement": score_engagement,
    "high_value_predicate": lambda s: s > 0.8,
    "enrich_premium_user": enrich_premium_user,
    "StoreResultSink": StoreResultSink,
})

result = await tapestry.run(RunRequest(parameters={"user_id": "u123"}))
```

---

**See also:** [Architecture — YAML Loader](../architecture/overview.md#yaml-pipeline-loader), [API — YAML Loader](../api/yaml-loader.md)
