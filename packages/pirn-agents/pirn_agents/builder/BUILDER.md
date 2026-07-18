# High-level Agent Builder (F19)

A thin, ergonomic facade over the knot-first API. The builder **generates**
ordinary `SubTapestry` knot graphs — it hides nothing and adds no capability.
Every graph it produces is identical to a hand-wired one and shares the engine's
caching and lineage. Drop to raw knots whenever you want.

## Quick start

```python
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents import Agent

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

Supported patterns: `Agent.patterns()` → `("naive_rag", "rag", "react")`.
`react` needs `llm` + `input`; `naive_rag`/`rag` needs `llm` + `memory` + a
string `input`.

## Auto-generated, stable knot ids

`build()` derives the top-level knot id from the *structure* of the request
(pattern, provider/tool references, options) via a SHA-256 digest — never from
wall-clock time or randomness. Building the same configuration twice yields the
same id, so lineage stays reproducible and cache hits line up. Pin a readable id
with `.name("my-agent")` (id becomes `agent.my-agent`).

## Config-driven agents: `AgentSpec`

`AgentSpec` is the declarative, serialisable counterpart of the builder. It
stores provider/tool **references** (plain strings) plus the pattern and its
options, and round-trips losslessly through dict/JSON/YAML.

```python
from pirn_agents import AgentSpec, AgentSpecLoader

spec = AgentSpecLoader.from_yaml("""
pattern: react
llm: my-llm
tools: [web_fetch, html_to_text]
options: {max_iterations: 6}
""")
assert AgentSpec.from_dict(spec.to_dict()) == spec   # round-trips
```

`from_json` uses only the standard library; `from_yaml`/`to_yaml` need the
`yaml` extra (`pip install "pirn-agents[yaml]"`) and are imported lazily, so a
bare `import pirn_agents` never pulls in PyYAML. Unknown or malformed fields are
rejected on load.

## Curated presets

`AgentPresets` are one-call recipes built entirely from the public builder API.
Each takes a caller-supplied `llm` (and `memory` where relevant) and accepts a
`tools=` override, so no preset hard-codes a vendor.

```python
from pirn_agents import AgentPresets

with Tapestry() as t:
    research = AgentPresets.research(llm=my_llm, input="...")          # web tools
    chat     = AgentPresets.rag_chat(llm=my_llm, memory=store, input="...")
    coder    = AgentPresets.coding(llm=my_llm, input="...", root="/srv/ws")
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
b.to_spec()       # -> declarative AgentSpec snapshot
```

`build()` is exactly equivalent to hand-wiring the pattern class. The two graphs
below are identical:

```python
# builder-generated
with Tapestry() as t:
    agent = Agent.builder().llm(llm).tools(tools).pattern("react", max_iterations=6).input("hi").build()

# hand-wired equivalent (the raw-knot form the builder emits)
from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage

with Tapestry() as t:
    agent = ReActLoop(
        messages=(AgentMessage(role="user", content="hi"),),
        llm=llm,
        tools=tuple(tools),
        max_iterations=6,
        _config=KnotConfig(id=agent_knot_id),   # any stable id you choose
    )
```

Because `build()` returns a plain `SubTapestry`, you can wire it as a parent of
your own hand-built knots (or vice versa) in a single `Tapestry` — builder-
generated and hand-wired knots compose freely with no boundary between them.
