# Prompt & System-Prompt Composition (PAE-F17 S1–S2)

Provider-neutral prompt templating and layered system-prompt composition. Every
type here is pure Python: no backend is imported, and rendering never executes
code.

## Authoring & versioning templates (S1)

A `PromptTemplate` pairs a `(name, version)` identity with a body containing
`{{ variable }}` slots and `{{> partial }}` includes.

```python
from pirn_agents.prompt.prompt_template import PromptTemplate

summarize = PromptTemplate(
    name="summarize",
    version="1.0.0",
    template="{{> preamble }}\n\nSummarize for {{ audience }}:\n{{ document }}",
    partials={"preamble": "You are a careful summarizer."},
    description="One-shot summarization prompt.",
)

summarize.variable_names()   # ('audience', 'document')  — the full set to supply
summarize.partial_names()    # ('preamble',)
print(summarize.render({"audience": "execs", "document": "..."}))
```

* **Versioning** — a new version is just another `PromptTemplate` with a bumped
  `version`. Versions order numerically (`"1.10.0" > "1.9.0"`).
* **Slots** — `{{ name }}`; names are whitelisted `[A-Za-z_][A-Za-z0-9_]*`.
  Dotted/attribute syntax (`{{ obj.attr }}`) is **not** a valid slot and stays
  literal, so there is no `str.format`-style attribute traversal.
* **Partials** — `{{> name }}` inlines `partials["name"]` exactly one level
  (no recursive expansion).

### Safe rendering

Rendering is injection-safe by construction:

* No `eval`, no `str.format` — substitution is a single left-to-right regex pass.
* Because the pass never re-scans inserted text, a variable value that itself
  contains `{{ ... }}` is **inert** and cannot inject a new slot or partial.
* Strict mode (default) raises `PromptRenderError` on a missing slot, an
  unknown partial, an unresolved placeholder, or a non-primitive value. Pass
  `strict=False` to leave unknown slots untouched instead.

```python
# A malicious value cannot exfiltrate a partial or re-expand:
tpl = PromptTemplate(name="chat", version="1.0.0", template="{{ user_input }}",
                     partials={"secret": "TOP-SECRET"})
tpl.render({"user_input": "{{> secret }}"})   # -> "{{> secret }}" (literal, inert)
```

## Registry usage (S1)

`PromptTemplateRegistry` is a namespaced, versioned lookup (modelled on the tool
registry). It holds one concrete type, so it does **not** mirror into the shared
`sweet_tea` registry — lookup is local.

```python
from pirn_agents.prompt.prompt_template_registry import PromptTemplateRegistry

reg = PromptTemplateRegistry()
reg.register(summarize)                       # namespace defaults to "default"
reg.register(summarize_v2, namespace="beta")

reg.get("summarize")                          # newest version resolved
reg.get("summarize", version="1.0.0")         # exact O(1) hit
reg.versions("summarize")                     # ['1.0.0', ...] lowest-first
reg.unregister("summarize", version="1.0.0")  # CRUD delete
```

Render inside a knot graph with `PromptRenderKnot(template=..., variables=...)`.

## System-prompt layering (S2)

`SystemPromptComposer` merges `SystemPromptLayer`s into one deterministic system
prompt. The canonical order is fixed and documented:

| order | kind      | typical content                         |
|-------|-----------|-----------------------------------------|
| 0     | `persona` | who the agent is                        |
| 1     | `policy`  | rules / guardrails                      |
| 2     | `tools`   | available tools and usage               |
| 3     | `memory`  | retrieved memory / summaries            |
| 4     | *custom*  | any other kind, in first-seen order     |

```python
from pirn_agents.prompt.system_prompt_composer import SystemPromptComposer
from pirn_agents.prompt.system_prompt_layer import SystemPromptLayer

layers = [
    SystemPromptLayer(kind="memory", content=memory_text),
    SystemPromptLayer(kind="persona", content="You are a helpful analyst."),
    SystemPromptLayer(kind="tools", content=tool_docs, title="# Tools"),
]
system_prompt = await composer.process(layers=layers)   # persona, then tools, then memory
```

* **Deterministic** — output is independent of input order.
* **Graceful** — empty/whitespace-only layers are skipped without blank
  sections; an all-empty set yields `""`.
* **Extensible** — any non-canonical `kind` is a custom layer appended after the
  canonical four, preserving first-seen order. Override the separator via
  `process(..., separator=...)`.
