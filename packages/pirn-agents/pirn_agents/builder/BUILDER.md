# High-level Agent Builder (F19)

A thin, ergonomic facade over the knot-first API. The builder **generates**
ordinary `SubTapestry` knot graphs — it hides nothing and adds no capability.
Every graph it produces is identical to a hand-wired one and shares the engine's
caching and lineage. Drop to raw knots whenever you want.

**This is one authoring surface, not a builder-only second one (ADR
"agents speaks core", WS6a).** Every pattern name reachable from `Agent.patterns()`
is aliased into the same `sweet_tea` registry core's own YAML loader resolves
`callable:` references through
(`AgentPatternRegistry.register_with_core_registry`), so `callable: react` in a
core pipeline document and `.pattern("react")` on the builder name the exact
same class through the exact same lookup. `AgentSpec` is a projection of core's
own `PipelineSpec` (`to_pipeline_spec`/`from_pipeline_spec`), not a parallel
schema. See `examples/agents_core_pipeline/` for a full agent pipeline written
in core's YAML vocabulary and validated by `tapestry-check`, and the agents
section of `docs/guides/yaml-pipelines.md` for the declarative-document shape.

## One authoring path, five views of it

There is one authoring path (sometimes called the builder's "spine" in
conversation, though that word names no class here). The pieces are not
alternatives to each other:

| Piece | Role |
|---|---|
| `AgentBuilder` | the authoring path's fluent front end, and what every other piece produces or consumes |
| `AgentSpec` | the builder as **data**: `.to_spec()`/`AgentBuilder.from_spec()` (dict/JSON/YAML), and `.to_pipeline_spec()`/`.from_pipeline_spec()` (core's own `PipelineSpec`) |
| `AgentReferences` | the caller-owned table binding a spec's reference labels to live objects — also usable as `known_callables` for core's loader (`.as_known_callables()`) |
| `AgentPresets` | **named entries** into the authoring path, each loaded from a saved core pipeline document under `builder/presets/*.yaml` |
| `AgentPatternRegistry` | the single pattern table all of the above consult, and the source of the aliases registered into core's own registry |

```
       .pattern()/.llm()/...                      .to_spec()               .to_pipeline_spec()
Agent.builder() ─────────────► AgentBuilder ─────────────────► AgentSpec ──┬──► JSON/YAML (legacy, deprecated)
                                 ▲     │                          │        └──► core PipelineSpec / YAML document
AgentPresets.builder_for() ──────┘     │ .build()                 │ Agent.from_spec(spec,
                                       ▼                          │        references=…)
                                  SubTapestry ◄──────────────────-┘
```

## Quick start

```python
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents.builder.agent import Agent

with Tapestry() as t:
    agent = (
        Agent.builder()
        .llm(my_llm_provider)          # any LLMProvider — no vendor assumed
        .tools(my_tools)               # a Toolset or a sequence of Tool
        .pattern("react", max_iterations=6)
        .input("What changed in the API?")
        .build()                       # -> SubTapestry, with an auto knot id
    )
run = await t.run(RunRequest())
response = run.outputs[agent.knot_id]  # knot_id is stable & derived, not random
```

## Every shipped pattern is reachable by name

`Agent.patterns()` returns every registered pattern name — 66 canonical names
plus the `rag` alias for `naive_rag` (67 total, `AgentPatternRegistry.pattern_names()`) —
the RAG patterns, the guardrail checks,
the multi-agent orchestrations (e.g. `.pattern("consensus")` →
`ConsensusPipeline`), the specialized agents, the structured-output
extractors, the ingestors, and the reasoning loops (e.g.
`.pattern("constitutional_filter")` → `ConstitutionalFilter`). None of them is
builder-invisible, and every one of them is also reachable through core's own
registry: `AbstractInverterFactory[Knot].create("react")` returns the exact
same class `.pattern("react")` does (`AgentPatternRegistry.pattern_names()`
confirms every name against that registry, not just its own table). See
[`PATTERNS.md`'s Full Pattern Reference](../PATTERNS.md#full-pattern-reference)
for the complete name-to-class table, kept in sync with the registry by
`tests/builder/test_pattern_registry_coverage.py`.

Patterns need different parts, so beyond `.llm()`, `.memory()` and `.tools()`
there is a general `.component(name, value)` slot keyed by the pattern's own
constructor parameter names. Ask what a pattern needs rather than guessing:

```python
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry

AgentPatternRegistry.required_components("graph_rag")    # ('graph_memory', 'llm')
AgentPatternRegistry.optional_parameters("graph_rag")    # ('hop_count',)
AgentPatternRegistry.describe("graph_rag")               # full contract, printable

with Tapestry() as t:
    agent = (
        Agent.builder()
        .llm(my_llm)
        .component("graph_memory", my_graph_store)
        .pattern("graph_rag", hop_count=2)
        .input("who reports to whom?")
        .build()
    )
```

A builder mid-configuration reports what is still missing:

```python
b = Agent.builder().llm(my_llm).pattern("self_query_rag")
b.missing_components     # ('store', 'embedder')
```

**The builder requires exactly what the class requires.** Required components
and optional knobs are read off the pattern class's constructor, not from a
hand-written table, so they cannot drift from the class. Two consequences worth
knowing:

- `.pattern("react")` now needs `.tools(...)` — pass `.tools(())` for a
  tool-less ReAct. `ReActLoop.__init__` has no default for `tools`, and the
  builder no longer supplies a hidden one that hand-wiring would not.
- A component or option the chosen pattern does not accept is an error, not a
  silent no-op — a graph wired differently from the one you asked for is worse
  than a build that stops.

## Auto-generated, stable knot ids

`build()` derives the top-level knot id from the *structure* of the request
(pattern, provider/tool references, options) via a SHA-256 digest — never from
wall-clock time or randomness. Building the same configuration twice yields the
same id, so lineage stays reproducible and cache hits line up. Pin a readable id
with `.name("my-agent")` (id becomes `agent.my-agent`).

`.input(...)`'s value is not baked into the generated graph as a constructor
kwarg — `build()` wraps it in a named core `Parameter` (`f"{knot_id}:{seed}"`),
a real graph node with its own lineage, rebindable from `RunRequest.parameters`
at run start without rebuilding the graph. Wiring an upstream `Knot` in as the
seed (rather than a literal) passes it through unchanged — it is already a
graph node.

## Config-driven agents: `AgentSpec`

`AgentSpec` is the builder as data — a projection of core's own
`PipelineSpec` (`to_pipeline_spec()`/`from_pipeline_spec()`), not a parallel
schema (ADR "agents speaks core", WS6a). It stores provider/tool/component
**references** (plain strings) plus the pattern and its options.

A spec cannot hold an open HTTP client or a live vector store, so it names them.
`AgentReferences` is the caller-owned table that binds those names back to real
objects — and `Agent.from_spec` turns the pair into a builder:

```python
from pirn.tapestry import Tapestry
from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader

# A core pipeline document — the same 9-node-type vocabulary any other
# pirn pipeline uses (see the agents section of docs/guides/yaml-pipelines.md).
spec = AgentSpecLoader.from_yaml("""
name: agent
nodes:
  - id: seed
    type: parameter
    type_: Any
  - id: agent
    type: knot
    callable: naive_rag
    parents: {query: seed}
    config: {top_k: 5}
""")

references = AgentReferences().register("my-llm", my_llm).register("kb", my_store)

with Tapestry() as t:
    agent = Agent.from_spec(spec, references=references).input("what changed?").build()
```

The older flat dialect (`pattern: naive_rag` / `llm: my-llm` / `memory: kb` /
`options: {...}` at the top level, with no `nodes:` list) loaded for one
deprecation cycle and is now deleted (PIR-864): `AgentSpecLoader.from_mapping`
rejects a mapping with no top-level `nodes:` key. Use `AgentSpec.from_dict()`/
`.to_dict()` directly if you already have that flat shape in hand — the
loader itself now speaks only the core-pipeline dialect above.

`register_tools(toolset)` binds each tool under its own `name`, which is the
label `to_spec()`/`to_pipeline_spec()` write for tools. An unregistered label
raises and lists the labels that *are* registered — a typo in a config file
fails at bind time rather than wiring a knot to nothing.

**A spec has no `input`.** It describes an agent's shape, not the question it is
asked, so one spec serves many inputs — `from_spec` returns a builder and you
supply `.input(...)` per call.

The trip is lossless in both directions, through either representation:

```python
b = Agent.builder().llm(my_llm).pattern("react", max_iterations=6)
assert Agent.from_spec(b.to_spec(), references=refs).to_spec() == b.to_spec()
assert AgentSpec.from_pipeline_spec(b.to_spec().to_pipeline_spec()) == b.to_spec()
```

`from_json` uses only the standard library; `from_yaml`/`to_yaml` need the
`yaml` extra (`pip install "pirn-agents[yaml]"`) and are imported lazily.
Unknown or malformed fields are rejected on load.

## Curated presets

`AgentPresets` are named entries into the authoring path, not a separate way
in. Each takes a caller-supplied `llm` (and `memory` where relevant) and
accepts a `tools=` override, so no preset hard-codes a vendor.

Each preset's *shape* — its pattern name and default options — is saved as a
core pipeline document under `builder/presets/{research,rag_chat,coding}.yaml`
and loaded through `AgentSpecLoader`, the same path every declarative agent
goes through (a caller-supplied `llm`/`memory`/`tools` is never in that
document — a saved shape is static, but which provider to use is exactly what
varies per call).

```python
from pirn_agents.builder.agent_presets import AgentPresets

with Tapestry() as t:
    research = AgentPresets.research(llm=my_llm, input="...")          # web tools
    chat     = AgentPresets.rag_chat(llm=my_llm, memory=store, input="...")
    coder    = AgentPresets.coding(llm=my_llm, input="...", root="/srv/ws")
```

`builder_for(name, **kwargs)` hands back the builder the preset uses, before it
becomes a graph — so a preset can be read as data, adjusted, or serialised. The
named call above is exactly this followed by `.build()`, so there is no second
copy of the defaults to drift:

```python
b = AgentPresets.builder_for("rag_chat", llm=my_llm, memory=store, input="...")
b.to_spec()                       # the preset's configuration as data — no Tapestry needed
b.pattern("naive_rag", top_k=9)   # keep chaining; it is an ordinary builder
with Tapestry():
    agent = b.build()
```

## Escape hatch — drop to raw knots

Nothing is builder-only. Every builder feature has a documented raw-knot
equivalent, and the builder exposes what it will generate so you can mix
generated and hand-wired knots in one graph.

Read back the resolved pieces and the target class before building:

```python
b = Agent.builder().llm(my_llm).tools(my_tools).pattern("react", max_iterations=6).input("hi")
b.pattern_class   # -> <class 'ReActLoop'>  (construct it yourself if you prefer)
b.knot_id         # -> the id build() will assign (derived, stable)
b.llm_provider, b.tool_list, b.memory_store, b.pattern_name, b.options, b.input_value
b.components          # -> every configured component, by parameter name
b.missing_components  # -> what the chosen pattern still needs
b.to_spec()           # -> declarative AgentSpec snapshot
```

`build()` is exactly equivalent to hand-wiring the pattern class with its seed
pre-wrapped in a `Parameter`. The two graphs below are identical:

```python
# builder-generated
with Tapestry() as t:
    agent = Agent.builder().llm(llm).tools(tools).pattern("react", max_iterations=6).input("hi").build()

# hand-wired equivalent (the raw-knot form the builder emits)
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage

with Tapestry() as t:
    seed = Parameter(
        name=f"{agent_knot_id}:messages",
        type_=tuple[AgentMessage, ...],
        default=(AgentMessage(role="user", content="hi"),),
        _config=KnotConfig(id=f"param:{agent_knot_id}:messages"),
    )
    agent = ReActLoop(
        messages=seed,
        llm=llm,
        tools=tuple(tools),
        max_iterations=6,
        _config=KnotConfig(id=agent_knot_id),   # any stable id you choose
    )
```

Because `build()` returns a plain `SubTapestry`, you can wire it as a parent of
your own hand-built knots (or vice versa) in a single `Tapestry` — builder-
generated and hand-wired knots compose freely with no boundary between them.
