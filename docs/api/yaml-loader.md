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

## Knot resolution: `Registry.fill_registry` + `AbstractInverterFactory[Knot]`

Pirn delegates Knot registration entirely to `sweet_tea.registry.Registry`. At import time, pirn auto-registers every Knot subclass defined under the `pirn` package via `Registry.fill_registry()`. The YAML loader resolves YAML `callable: <name>` strings through `sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`, which performs a typed lookup against the registry and returns the class definition (instantiation is deferred so the loader can pass its assembled kwargs).

**For your own knots**, call `Registry.fill_registry()` from your project's package init:

```python
# myapp/__init__.py
from sweet_tea.registry import Registry

Registry.fill_registry()   # scans myapp/ and registers every class defined here
```

After import, your knots are resolvable by name from any YAML pipeline:

```python
tapestry = load_pipeline(yaml_text)     # no known_callables needed
```

For one-off registrations (e.g. registering an `@knot`-decorated factory), use `Registry.register` directly:

```python
from sweet_tea.registry import Registry
Registry.register("my_alias", MyKnot, library="myapp")
```

To scope a manual lookup to a specific library, pass `library=` to `AbstractInverterFactory[Knot].create`:

```python
from sweet_tea.abstract_inverter_factory import AbstractInverterFactory
from pirn.core.knot import Knot

knot_class = AbstractInverterFactory[Knot].create("my_knot", library="myapp")
```

`known_callables` passed to `load_pipeline` still takes priority over the registry-based resolution.

---

**See also:** [YAML Pipelines Guide](../guides/yaml-pipelines.md), [Architecture — YAML Loader](../architecture/overview.md#yaml-pipeline-loader)

---

## YAML vs Python: what cannot be declared in YAML

Some pirn constructs are Python-only. They can be *referenced* from YAML (as `type: knot` with a `callable:` pointing to their class), but they cannot be *declared* inline in a YAML pipeline spec.

| Construct | Status | How to use with YAML |
|-----------|--------|----------------------|
| `SubTapestry` | Python-only | Subclass in Python, reference via `callable:` |
| `LoopSubTapestry` | Python-only | Subclass in Python, reference via `callable:` |
| `Optional(MyKnot, ...)` | Python-only | Wrap in Python, reference the wrapper via `callable:` |
| Assembler knots | Python-only | Write in Python, reference via `callable:` |

**Example — SubTapestry referenced from YAML:**

```python
# myapp/stages.py
class ValidateOrder(SubTapestry):
    async def process(self, order: Order, **_) -> Knot:
        p = Parameter("order", Order, default=order, _config=KnotConfig(id="order"))
        authorize_payment(order=p, _config=KnotConfig(id="payment"))
        return check_inventory(order=p, _config=KnotConfig(id="inventory"))
```

```yaml
- id: validate
  type: knot
  callable: myapp.stages.ValidateOrder
  parents:
    order: ingest
```

The outer pipeline topology lives in YAML; the inner pipeline logic stays in `process()` in Python.

---

## Field name configuration

Several built-in domain knots accept caller-supplied field name parameters so they work with any input schema without modifying the knot. Pass them via the `config:` dict on any `knot` node.

### Example — `VCFFilter` with custom field names

```yaml
- id: filter_variants
  type: knot
  callable: VCFFilter
  parents:
    rows: fetch_rows
    min_qual: qual_threshold
    max_af: af_threshold
  config:
    qual_field: "qscore"       # default: "qual"
    af_field: "allele_freq"    # default: "af"
```

Without `config:`, the knot uses its default field names (matching the original schema). Pass custom names when your data uses different keys.

### Knots with configurable field names (added in v0.3.0)

| Knot | Parameters | Defaults |
|------|-----------|---------|
| `VCFFilter` | `qual_field`, `af_field` | `"qual"`, `"af"` |
| `ProductionRateNormalizer` | `rate_field` | `"rate"` |
| `GasLiftOptimizer` | `pressure_field`, `rate_field` | `"pressure"`, `"rate"` |
| `EspHealthMonitor` | `freq_field`, `current_field` | `"frequency"`, `"current"` |
| `FlaringMeasurementProcessor` | `volume_field`, `duration_field` | `"volume"`, `"duration"` |
| `DowntimeEventClassifier` | `reason_field`, `duration_field` | `"reason"`, `"duration"` |
| `RodPumpOptimizer` | `stroke_field`, `load_field` | `"stroke_rate"`, `"rod_load"` |
| `SeparatorTestProcessor` | `gor_field`, `wc_field` | `"gor"`, `"water_cut"` |
| `TankGaugingProcessor` | `level_field`, `temp_field` | `"level"`, `"temperature"` |
| `CorrosionRateEstimator` | `rate_field`, `inhibitor_field` | `"corrosion_rate"`, `"inhibitor_concentration"` |
| `GasChromatographyAnalyzer` | `component_field`, `pct_field` | `"component"`, `"mole_percent"` |
| `MudLoggingIngester` | `depth_field`, `gas_field` | `"depth"`, `"gas_reading"` |

Missing required fields now raise `KeyError` with a message listing the expected key and the keys actually present — previously they silently used a default value of `0` or `None`.
