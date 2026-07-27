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

## Operator-tunable built-in prompts (WS6-S1)

Every prompt literal that ships inside `pirn_agents` is declared as a
`PromptBinding` class attribute rather than a bare `str`, and read through
`.resolve()` at call time. That single indirection is what lets an operator
retune a shipped prompt **without editing Python**.

### Resolution order

`PromptBinding.resolve()` applies exactly three steps, in this order:

| # | source | wins when |
|---|--------|-----------|
| 1 | **subclass override** | a public, documented `ClassVar[str]` has been changed away from the built-in default |
| 2 | **registered / loaded template** | the catalog holds `(namespace, name[, version])` |
| 3 | **built-in default** | nothing else matched — the literal that shipped in the wheel, byte for byte |

Step 1 comes first because a subclass author asked for specific text *in code*;
deployment configuration must not silently defeat that. Step 3 is a plain
attribute read, so a converted site costs nothing and cannot change delivered
text when no pack is loaded.

### Converting a site — private attribute (the common case)

Before:

```python
class ChainOfThought(Knot):
    _system_prompt: str = (
        "Think step-by-step. Show your reasoning before stating your final answer."
    )

    async def process(self, prompt: str, llm: LLMProvider, **_: Any) -> AgentResponse:
        messages = [
            {"role": "system", "content": type(self)._system_prompt},
            ...
        ]
```

After:

```python
from typing import Any, ClassVar

from pirn_agents.prompt.prompt_binding import PromptBinding


class ChainOfThought(Knot):
    _system_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.chain_of_thought.chain_of_thought.system_prompt",
        default="Think step-by-step. Show your reasoning before stating your final answer.",
    )

    async def process(self, prompt: str, llm: LLMProvider, **_: Any) -> AgentResponse:
        messages = [
            {"role": "system", "content": type(self)._system_prompt.resolve()},
            ...
        ]
```

Four mechanical edits: add `ClassVar` to the `typing` import, add the
`PromptBinding` import, wrap the literal, append `.resolve()` at the call site.
The literal itself is **moved, never retyped** — prompt text stays byte-identical.

### Converting a site — public, subclass-overridable `ClassVar[str]`

A handful of sites document a public class var as an override point
(`ReflectionCheck.reflection_prompt`, `Planner.planning_instruction`). Keep the
attribute a readable `str` and derive it from the binding, then pass it back to
`resolve()` so an override is detected:

```python
class ReflectionCheck(Knot):
    #: Registry binding backing :attr:`reflection_prompt`.
    _reflection_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="control.reflection_check.reflection_prompt",
        default="You are an agent reflection assistant. ...",
    )

    #: Override on a subclass to customise; a subclass value takes precedence
    #: over any registered/loaded template.
    reflection_prompt: ClassVar[str] = _reflection_prompt.default

    async def process(self, ...):
        wire_messages = (
            {
                "role": "system",
                "content": type(self)._reflection_prompt.resolve(type(self).reflection_prompt),
            },
            ...
        )
```

The binding must be declared **before** the public attribute that reads its
`.default`. A subclass that re-declares the *same* text as the built-in is
indistinguishable from not overriding, so a loaded pack still wins there —
overriding means changing the text.

### Converting a site — a prompt that embeds runtime data

Most prompts interleave instruction text with runtime values — a target
language, a tool name, a rendered evidence block. Bind the **whole** prompt as a
`{{ slot }}` template and read it through `resolve`'s sibling, `render`:

```python
class _CodeGenerator(Knot):
    _system_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.specialized_agents._code_generator.system_prompt",
        default=(
            "You are a senior {{ language }} engineer. Reply with "
            "working {{ language }} code only — no prose, no "
            "markdown fences, no explanation."
        ),
    )

    async def process(self, task: str, llm: LLMProvider, language: str, **_: Any) -> str:
        chat_messages = [
            {
                "role": "system",
                "content": type(self)._system_prompt.render({"language": language}),
            },
            {"role": "user", "content": task},
        ]
```

`render` runs `resolve` and then **one** non-strict substitution pass. That
single pass is what makes the built-in default and a loaded pack behave
identically: `resolve` consults the catalog with no variables, so a registered
body arrives with its markers still literal, exactly like the shipped default.
An operator may therefore move, repeat, or drop a slot; the call site only
supplies values.

* Values are stringified by `PromptTemplate`. Pre-format anything whose text
  must be exact — `repr(list(labels))`, `json.dumps(schema, sort_keys=True)` —
  at the call site rather than relying on `str()`.
* A slot the call site does not supply stays literal instead of raising
  mid-turn, and a substituted *value* containing `{{ ... }}` is inert.
* Binding only the *static run* around an interpolation was the alternative and
  was rejected: several defaults would have been sentence fragments, leaving an
  operator nothing coherent to override.

Use plain `resolve()` for the static sites; it returns the default byte for byte
and costs nothing.

### Converting a site — a prompt supplied as a parameter default

A few sites let the caller pass the prompt, defaulting to the built-in
(`SemanticMemoryUpsert.fact_extraction_prompt`, `RagTool(system_prompt=...)`,
`LlmInjectionClassifier(system_prompt=...)`). Keep the parameter a `str` — a
`PromptBinding` must never leak where a `str` is expected — and resolve **in the
method that builds the messages**, not in `__init__`, so a pack loaded after
construction still applies:

```python
async def classify(self, text: str) -> InjectionVerdict:
    messages = [
        {
            "role": "system",
            "content": type(self)._system_prompt_binding.resolve(self._system_prompt),
        },
        ...
    ]
```

Passing the stored value as `declared` reuses the documented precedence exactly:
an explicit caller value wins, otherwise a pack, otherwise the built-in. For a
knot input whose signature default must stay a readable `str`, declare it as
`_binding.default` (a plain attribute read at class-body time) and pass the
received value back through `resolve` in `process()`.

### Binding names

The name is the owning module's dotted path under `pirn_agents`, plus the
attribute name with any leading underscore stripped:

| file | attribute | binding name |
|------|-----------|--------------|
| `control/reflection_check.py` | `reflection_prompt` | `control.reflection_check.reflection_prompt` |
| `specializations/reflection/self_critique_revise.py` | `_critique_system` | `specializations.reflection.self_critique_revise.critique_system` |

This is mechanically derivable and collision-free (three different classes ship
a `_revision_system`; their module paths keep them apart). Built-ins resolve in
the `pirn_agents` namespace, so an operator pack cannot collide with an
application's own templates. A private module keeps its leading underscore in
the path (`specializations.structured_output._json_extractor_attempt.system_prompt`)
— the rule strips the underscore from the *attribute*, not from the module.

### Prompt packs — the operator side

A *prompt pack* is a JSON/YAML file listing template overrides:

```yaml
namespace: pirn_agents            # optional; defaults to the built-in namespace
templates:
  specializations.chain_of_thought.chain_of_thought.system_prompt: |
    Think step-by-step, and answer in French.
  control.reflection_check.reflection_prompt:
    version: "2.0.0"
    description: Terser reflection gate.
    template: "Answer yes or no."
```

Each entry is a bare string (the body, at version `1.0.0`) or a mapping with an
explicit `template` plus optional `version` / `description` / `partials`.

Packs reach the running process two ways:

```bash
# 1. zero code change — os.pathsep-separated list of pack files
export PIRN_AGENTS_PROMPT_PACKS=/etc/pirn/prompts.yaml:/etc/pirn/overrides.json
```

```python
# 2. explicit wiring at application start-up
from pirn_agents.prompt.prompt_catalog import PromptCatalog

PromptCatalog.shared().load_path("prompts.yaml")
PromptCatalog.shared().load_path(untrusted_name, allowed_root="/etc/pirn/prompts")
```

* The env var is read once, when `PromptCatalog.shared()` is first touched. A
  malformed pack raises there rather than being ignored — a prompt override that
  silently did nothing would be worse than a loud start-up failure.
* Re-loading the same `(namespace, name, version)` **replaces** it, so packs are
  idempotent.
* Rendering a loaded template is non-strict: a slot the call site does not supply
  stays literal `{{ text }}` rather than raising mid-turn inside an agent.
* Pass `allowed_root` when the path may come from an untrusted or multi-tenant
  source; it is vetted by the shared `PathGuard`.
* **PyYAML is an optional extra.** Nothing here imports it at module level; a
  `.yaml`/`.yml` pack pulls it in lazily via `_require`, which raises
  `pip install "pirn-agents[yaml]"` when it is missing. JSON packs and every
  built-in default work with the base install.

For tests and multi-tenant embedding, pass an explicit catalog instead of
touching the process-wide one:

```python
binding.resolve(catalog=my_catalog)
PromptCatalog.reset_shared()   # test teardown
```

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
