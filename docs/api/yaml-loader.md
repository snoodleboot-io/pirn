# YAML Loader API

---

## `load_pipeline()`

```python
from pirn import load_pipeline

tapestry = load_pipeline(
    yaml_text,
    *,
    tapestry=None,
    known_callables=None,
    allowed_module_prefixes=None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `yaml_text` | `str` | YAML source text |
| `tapestry` | `Tapestry \| None` | Tapestry to populate; a new one is created if omitted |
| `known_callables` | `Mapping[str, Any] \| None` | Name-to-callable map used in strict mode |
| `allowed_module_prefixes` | `list[str] \| None` | Restrict loose-mode imports to these module prefixes |

Returns a fully-constructed `Tapestry` with all knots registered and ready to run.

---

## `PipelineSpec` — top-level YAML fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str \| None` | `null` | Human-readable label |
| `description` | `str \| None` | `null` | Pipeline description |
| `allow_callable_refs` | `bool` | `false` | Enable loose mode (dotted import paths) |
| `allowed_module_prefixes` | `list[str] \| None` | `null` | Restrict loose-mode imports to these prefixes |
| `nodes` | `list[NodeSpec]` | `[]` | Ordered list of node declarations |

---

## Common node fields

All node types inherit these fields.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Unique node identifier within the pipeline |
| `type` | `str` | required | Node type (see below) |
| `description` | `str \| None` | `null` | Human-readable description |
| `tags` | `list[str]` | `[]` | Arbitrary labels |
| `error_policy` | `str` | `"skip_if_parent_failed"` | `"skip_if_parent_failed"`, `"require_all_parents"`, or `"receive_errors"` |
| `validate_io` | `bool` | `true` | Enable Pydantic input/output validation |

---

## Node types

### `parameter`

An external input value bound at run time via `RunRequest.parameters`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type_` | `str` | required | Python type as a dotted path: `"int"`, `"str"`, `"list[dict]"`, `"myapp.models.User"` |
| `has_default` | `bool` | `false` | Whether a default value is provided |
| `default` | `Any` | `null` | Default value (used when `has_default` is `true`) |

```yaml
- id: user_id
  type: parameter
  type_: str
```

---

### `knot`

A typed async processing node.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `callable` | `str` | required | Name in `known_callables`, or dotted import path in loose mode |
| `parents` | `dict[str, str]` | `{}` | Maps `process()` parameter names to parent node ids |
| `config` | `dict[str, Any]` | `{}` | Static values passed as `process()` kwargs (not from parents) |

```yaml
- id: score_text
  type: knot
  callable: score_text
  parents:
    text: user_input
  config:
    threshold: 0.8
```

---

### `source`

A zero-parent producer (file read, DB query, API fetch, etc.).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `callable` | `str` | required | Callable reference |

```yaml
- id: fetch_records
  type: source
  callable: FetchRecordsSource
```

---

### `sink`

A terminal consumer with no return value.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `callable` | `str` | required | Callable reference |
| `parents` | `dict[str, str]` | `{}` | Maps `process()` parameter names to parent node ids |
| `config` | `dict[str, Any]` | `{}` | Static config values |

```yaml
- id: write_result
  type: sink
  callable: WriteResultSink
  parents:
    data: score_text
```

---

### `branch`

Routes one input value to one of several named output paths. Non-selected paths become `Skipped`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | `str` | required | Node id whose output is passed to the selector |
| `selector` | `str` | required | Callable reference: `(value) -> str` returning a branch name |
| `branches` | `list[str]` | required | All valid branch names (at least one) |

```yaml
- id: route
  type: branch
  input: classify
  selector: route_selector
  branches:
    - clean
    - toxic
    - uncertain
```

---

### `gate`

Passes a value through or produces `Skipped` based on a predicate.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | `str` | required | Node id whose output is tested |
| `predicate` | `str` | required | Callable reference: `(value) -> bool` |

```yaml
- id: quality_gate
  type: gate
  input: score
  predicate: is_high_quality
```

---

### `map`

Applies a knot to each element of a collection, producing a list of results.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `over` | `str` | required | Node id producing the collection |
| `each` | `str` | required | Callable reference applied per element |
| `bind` | `str` | required | Parameter name the element is bound to in `each` |
| `shared` | `dict[str, Any]` | `{}` | Static values shared across all per-element calls |

```yaml
- id: process_items
  type: map
  over: fetch_ids
  each: process_single
  bind: item_id
  shared:
    model_version: "v2"
```

---

### `reduce`

Folds a list into a single value.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `of` | `str` | required | Node id producing the list |
| `combine` | `str` | required | Callable reference: `(list) -> value` or `(a, b) -> value` for pairwise reduce |
| `has_initial` | `bool` | `false` | Whether an initial value is provided |
| `initial` | `Any` | `null` | Initial accumulator value (pairwise reduce only) |

```yaml
- id: total
  type: reduce
  of: scored_items
  combine: sum_scores
  initial: 0
  has_initial: true
```

---

### `aggregator`

Combines multiple parent outputs via a merge function.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `combine` | `str` | required | Callable reference: `(dict[str, Any]) -> value` |
| `parents` | `dict[str, str]` | `{}` | Maps argument names to parent node ids |

```yaml
- id: merged
  type: aggregator
  parents:
    left: process_left
    right: process_right
  combine: merge_results
```

---

## `KnotRegistry`

For `Knot` subclasses, register them globally so the loader can resolve them by name without passing `known_callables` on every call.

```python
from pirn.yaml_loader.knot_registry import KnotRegistry

KnotRegistry.register("MyKnot", MyKnot)
```

Auto-discover all `Knot` subclasses in a package using `sweet_tea`:

```python
from sweet_tea.registry import Registry

Registry.fill_registry(module="myapp")  # scans myapp recursively
tapestry = load_pipeline(yaml_text)     # no known_callables needed
```

`known_callables` passed to `load_pipeline` takes priority over `KnotRegistry`.

---

**See also:** [YAML Pipelines Guide](../guides/yaml-pipelines.md), [Architecture — YAML Loader](../architecture/overview.md#yaml-pipeline-loader)
