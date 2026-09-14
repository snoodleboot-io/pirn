# YAML Pipelines

pirn pipelines can be declared entirely in YAML and loaded at runtime with `PipelineLoader.load_yaml()`. The YAML loader is a strict-by-default tool that translates a pipeline definition file into a live `Tapestry`.

---

## Entry point

```python
from pirn.core.run_request import RunRequest
from pirn.yaml_loader.pipeline_loader import PipelineLoader

tapestry = PipelineLoader.load_yaml(
    yaml_text,                              # str or Path
    known_callables={"my_fn": my_fn},      # name → callable
    tapestry=existing_tapestry,            # optional; new Tapestry() if omitted
)

result = await tapestry.run(RunRequest(parameters={"x": 5}))
```

`PipelineLoader.load_yaml` returns a fully-constructed `Tapestry` with all knots registered. You can run it immediately or attach emitters before running.

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

A `Mapping[str, Any]` passed to `PipelineLoader.load_yaml`. Values can be:

- Plain callables (sync or async functions)
- `KnotFactory` instances (from `@knot` decorator)
- `Knot` subclasses

The loader's `_resolve_callable` checks `known_callables` first. In strict mode, if a name is not found, `ValueError` is raised. In loose mode, the loader falls back to a dotted import.

### Auto-discovery with `fill_registry`

Pirn calls `Registry.fill_registry()` on its own tree at import time, so every built-in pirn Knot is resolvable by name out of the box. **For your own knots, you must call** `Registry.fill_registry()` **from your project's package init** — otherwise the loader will not find them:

```python
# myapp/__init__.py
from sweet_tea.registry import Registry

Registry.fill_registry()   # scans myapp/ and registers every class defined in it
```

After that, any `Knot` subclass under `myapp/` is resolvable from YAML by its snake-case class name, with no `known_callables` argument needed.

`known_callables` remains supported as a per-call override with the highest priority — useful in tests or when the same callable needs multiple pipeline-specific aliases.

**For the full registration story** — manual `Registry.register` calls, registering `@knot`-decorated factories, library scoping, troubleshooting, and lifecycle rules — see the [Knot Registration guide](knot-registration.md).

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
tapestry = PipelineLoader.load_yaml(yaml_text, known_callables={
    "fetch_user": fetch_user,
    "score_engagement": score_engagement,
    "high_value_predicate": lambda s: s > 0.8,
    "enrich_premium_user": enrich_premium_user,
    "StoreResultSink": StoreResultSink,
})

result = await tapestry.run(RunRequest(parameters={"user_id": "u123"}))
```

---

---

## YAML vs Python: what cannot be declared in YAML

Some pirn constructs are Python-only. They can be *referenced* from YAML (as `type: knot` with a `callable:` pointing to their class), but they cannot be *declared* inline in a pipeline spec.

| Construct | Status | How to use with YAML |
|-----------|--------|----------------------|
| `SubTapestry` | Python-only | Subclass in Python, reference via `callable:` |
| `LoopSubTapestry` | Python-only | Subclass in Python, reference via `callable:` |
| `Optional(MyKnot, ...)` | Python-only | Wrap in Python, reference the wrapper via `callable:` |
| Assembler knots | Python-only | Write in Python, reference via `callable:` |

The YAML loader supports 9 node types: `parameter`, `knot`, `source`, `sink`, `branch`, `gate`, `map`, `reduce`, and `aggregator`. Constructs that require custom Python logic (inner pipelines, conditional wrapping, assembler composition) must be implemented as a class and referenced from YAML rather than declared inline.

**See also:** [YAML Loader API — Field name configuration](../api/yaml-loader.md#field-name-configuration) for configuring domain knot schema params from YAML.

---

## Agents

`pirn-agents`' 65 shipped agentic patterns (ReAct, the RAG family, guardrail checks, multi-agent orchestrations, structured-output extractors, …) are ordinary `SubTapestry` knots, so they need nothing agents-specific to reach from YAML — every pattern name is a `callable:` reference like any other.

### Pattern names resolve like any other knot

`pirn_agents`, at import time, aliases every name `AgentPatternRegistry` (and `Agent.patterns()`) advertises into the same `sweet_tea` registry this loader's `_resolve_callable` reads (`AgentPatternRegistry.register_with_core_registry`). No `known_callables` entry is needed for a pattern name — `callable: react` resolves exactly the way `callable: object_store_read_source` does for a core-shipped knot:

```yaml
nodes:
  - id: seed
    type: parameter
    type_: Any

  - id: agent
    type: knot
    callable: react            # resolves via the shared registry, no known_callables needed
    parents:
      messages: seed
    config:
      tools: []
      max_iterations: 3
```

A pattern's runtime seed (the parameter the high-level builder's `.input(...)` feeds — `messages` for `react`, `query` for the RAG family, `task` for planning loops — see `AgentPatternRegistry.descriptor(name).seed`) is always its own graph input, never baked into `config`. A hand-authored document supplies it exactly as-shaped: `react`'s `messages` wants a `tuple[AgentMessage, ...]`/`list[AgentMessage]`, not a bare string — the string-to-message convenience `AgentBuilder.input(...)` provides is a builder-only nicety (see `docs/guides/knot-registration.md` and `pirn_agents/builder/BUILDER.md`), not something this loader performs.

### Live references (LLM providers, memory stores, tools)

A pattern's other required components are usually live objects — an `LLMProvider`, a `MemoryStore`, a `Tool` — that cannot be written into YAML text. `AgentReferences.as_known_callables()` adapts a caller-owned label → object table into this loader's `known_callables`, so a `source` node can name the label as its `callable:`:

```python
from pirn.yaml_loader.pipeline_loader import PipelineLoader
from pirn_agents.builder.agent_references import AgentReferences

references = AgentReferences().register("llm", my_llm_provider)
tapestry = PipelineLoader.load_yaml(yaml_text, known_callables=references.as_known_callables())
```

```yaml
nodes:
  - id: llm_provider
    type: source
    callable: llm               # resolved via known_callables, not the registry
  - id: agent
    type: knot
    callable: react
    parents: {messages: seed, llm: llm_provider}
```

See `examples/agents_core_pipeline/` for the complete, `tapestry-check`-validated version of this pipeline.

### `AgentSpec` — the declarative shape as a core pipeline document

`AgentSpec` (pattern + provider/tool/component references + options — the config-driven counterpart of the fluent builder) is a projection of `PipelineSpec`: `AgentSpec.to_pipeline_spec()`/`AgentSpec.from_pipeline_spec()` round-trip losslessly through it, and `AgentSpecLoader.from_yaml`/`from_json`/`from_path`/`to_yaml`/`to_json` read and write a core pipeline document directly (a top-level `nodes:` key). The older flat dialect (`pattern:`/`llm:`/`memory:`/`tools:`/`components:`/`options:` at the top level, no `nodes:` list) loaded for one deprecation cycle and is now deleted (PIR-864) — `AgentSpecLoader.from_mapping` rejects a mapping with no `nodes:` key; use `AgentSpec.from_dict`/`.to_dict()` directly if you already have that flat shape in hand. See `pirn_agents/builder/BUILDER.md`'s "Config-driven agents" section for the full walkthrough, including how references round-trip through tagged `parameter` nodes.

---

**See also:** [Architecture — YAML Loader](../architecture/overview.md#yaml-pipeline-loader), [API — YAML Loader](../api/yaml-loader.md), and `pirn_agents/builder/BUILDER.md` in the `pirn-agents` package for the full authoring-surface walkthrough
