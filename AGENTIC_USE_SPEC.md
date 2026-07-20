# AGENTIC_USE.md — format specification

> This file defines the **AGENTIC_USE.md** format. It is the canonical definition;
> other repositories should link here rather than restate it.
>
> An AGENTIC_USE.md is a **usage contract for an LLM working in a codebase**. It
> answers "how do I use this correctly?" — not "how does this work internally?"
> (architecture docs) and not "what does this project do?" (README).

---

## 1. What the format is for

Prose documentation is written for humans who will read it once and build a
mental model over weeks. An agent reads a file once, in a single context, and
must produce correct code immediately. The format optimises for that:

| Property | Why it matters to an agent |
|---|---|
| **Fixed section order** | The agent can predict where an answer lives and stop reading early. |
| **Contract-first** | "Must implement X, must not do Y" is directly checkable against generated code. |
| **Named anti-patterns** | Pre-empts the specific wrong thing a model is *likely* to produce. |
| **Runnable examples** | Copy-adapt beats synthesise-from-description. |
| **Hierarchical** | The agent loads the root file plus one leaf, not the whole corpus. |

Design rule of thumb: **every section should change what the agent writes.**
If a section would not alter generated code, cut it.

---

## 2. Placement and scope

One AGENTIC_USE.md per **coherent unit of use** — a unit a caller consumes
without needing to know its siblings.

```
<repo>/AGENTIC_USE.md                    ← level 0: the framework's core contract
<repo>/<package>/AGENTIC_USE.md          ← level 1: a domain / installable package
<repo>/<package>/<area>/AGENTIC_USE.md   ← level 2: a leaf area (filters, genomics, …)
```

**Rules**

- Place the file **at the package root it documents**, beside the code, so the
  path itself scopes it.
- **Depth is driven by divergence, not size.** Split a level only when the
  sub-area has its own mental model, its own anti-patterns, or its own
  dependencies. A large-but-uniform package stays one file.
- **Never duplicate a parent's content.** A child assumes the parent has been
  read and covers only what is *additionally* true. State that assumption in
  the child's opening line.
- Every parent ends with a **child index** (§3.9) and every child opens with a
  **parent pointer**. The graph must be navigable in both directions.

---

## 3. Section skeleton

Sections appear **in this order**. Levels 0–1 use the full set; leaf files use
the core five (marked ●). Omit a section entirely rather than writing a stub.

### 3.0 Title and thesis — *required*

```markdown
# AGENTIC_USE — <unit name> <version>

> <One sentence: what this unit is, followed by an explicit
> statement of what it does NOT do.>
```

The negative half is load-bearing — it is the cheapest way to stop an agent
inventing capabilities. From pirn's root file:

> …composes work as a DAG of *knots* … — it does NOT execute work itself,
> supply data, or manage infrastructure.

Child files add a parent pointer immediately after:
`> Assumes [../AGENTIC_USE.md](../AGENTIC_USE.md) has been read.`

### 3.1 ● Mental model — *required*

Two to four paragraphs establishing the vocabulary and the **object lifecycle**:
what the core types are, how they are constructed, how they relate, and when
things happen. Bold each term on first use — those become the words used for
the rest of the file.

Cover, where applicable: the container/unit distinction, where wiring happens
(constructor vs. method vs. config), what is immutable and when it freezes, and
the shape of results.

### 3.2 Install / prerequisites — *optional*

Only when the unit needs a non-default extra, dependency, or credential. One
code block. Skip it at level 0 if the README covers it.

### 3.3 ● Source map — *required*

An annotated tree. **The annotation is the point** — a bare tree is worthless.

```
package/
├── core/
│   ├── knot.py        ← Knot base class: constructor wiring, freeze guard
│   └── knot_config.py ← KnotConfig: id (required), error_policy, validate_io
└── nodes/             ← composite node types; one file per node kind
```

- Annotate with **what a caller uses it for**, not what it contains.
- Expand to file level for anything a caller touches; collapse whole
  directories to one line for internals (`engine/ ← internal execution engine`).
- Aim for one screen. If it does not fit, that is a signal to split the level.

### 3.4 ● Canonical pattern — *required*

The **shortest complete, runnable** example. Complete means imports through to
output, with the expected result in a trailing comment.

If the unit genuinely offers distinct construction styles, show them as
labelled variants (`### A — decorator`, `### B — subclass`, `### C — YAML`) and
say in one clause **when each is preferred** — an agent given three
alternatives with no selection criterion will pick arbitrarily.

Do not show more than three. Extra ways of doing the same thing belong in
Worked examples or nowhere.

### 3.5 Extension points — *level 0–1*

One subsection per type a caller subclasses or implements. Each **must** carry:

- **Contract:** what to subclass, the exact method signature to implement,
  what is required in it.
- **Must not:** the failure cases, **with the actual error and when it fires**
  ("raises `TypeError` at class-definition time"). An agent that knows the
  error message can self-correct; one told "don't do that" cannot.
- A minimal example, annotated where a line is non-obvious.
- Where implementations live and how they are named, if there is a convention.

### 3.6 ● Anti-patterns — *required*

The highest-value section. Each entry uses a three-line structure:

```markdown
### <The wrong thing, stated as an action>

**Looks right because:** <the plausible reasoning that leads here>
**Wrong because:** <mechanism — what actually breaks, and how it surfaces>
**Do instead:** <the correct construction>
```

- The **Looks right because** line is not padding. It is the recognition key:
  it lets the agent notice it is *currently reasoning that way*.
- Prefer failures that are **silent or delayed**. An error that fires loudly at
  construction time teaches itself; one that silently produces wrong lineage
  does not.
- Source these from real mistakes — code review, bug reports, watching an agent
  work — not from imagination. Five observed anti-patterns beat twenty guessed.
- Leaf files may compress each to a single `**Wrong:** … **Instead:** …` line.

### 3.7 ● Constraints and gotchas — *required*

A flat bullet list of facts that do not fit elsewhere. Each bullet: **bold
claim**, then the consequence and the remedy.

```markdown
- **`tapestry.run()` is a coroutine**: always `await` it. Calling without
  `await` returns a coroutine object and nothing executes.
```

Include hard limits and formats (id charsets, size caps), defaults with
non-obvious behaviour, backend/platform restrictions, and **security
boundaries** — anything that executes arbitrary input, deserialises untrusted
data, or ships unauthenticated must appear here explicitly.

### 3.8 Worked examples — *level 0–1, optional*

One or two **realistic** end-to-end scenarios, past the toy stage: composition,
error paths, inspecting results. Show a failure case, not only the happy path.

### 3.9 ● Quick reference — *required*

A two-column `| Task | How |` table. Tasks phrased as the **intent an agent
arrives with** ("Handle upstream errors"), not as API names. The `How` column
is a copyable fragment.

This is the section most likely to be read alone — it must stand without the
prose above it.

### 3.10 Child index — *required if children exist*

A table linking every child AGENTIC_USE.md, one line each on when to read it,
plus any install extra. Instruct the agent to read the child *alongside* this
file. **Verify these paths resolve** — see §6.

### 3.11 Footer

`*Generated for agent use. Covers <unit> <version>.*`

---

## 4. Writing rules

**Voice.** Present tense, active, imperative. State mechanism, never
motivation: "Knots are frozen after `__init__`; `__setattr__` raises" — not
"we felt immutability was cleaner."

**Precision over completeness.** Exact identifiers, exact signatures, exact
error text. A guide covering 60% of the API accurately is worth more than one
covering 100% approximately, because the agent cannot tell which parts to
trust.

**Every code block runs.** No `...` in a block presented as complete; no
pseudocode. Elide with a commented placeholder that makes the omission obvious
(`raw = ...  # some upstream knot`).

**Show the error.** Wherever behaviour is enforced, quote the message the
developer will actually see.

**Length.** Level 0: 300–600 lines. Level 1: 150–350. Level 2: 80–150. Past the
ceiling, split. The budget exists because the file competes for context with
the code the agent is actually writing.

**Do not include:** rationale/history, roadmaps, changelogs, benchmarks,
contribution instructions, internal implementation detail a caller cannot
observe, or anything already in the README. Every one of those spends context
without changing output.

---

## 5. Variant: DSL / output-format guides

A unit whose "API" is a **language the agent emits** (a config format, a query
DSL, a markup language) needs a different skeleton. Signal the variant in the
title: `# AGENTIC_USE.md — authoring <lang> for agents`.

| Standard section | DSL equivalent |
|---|---|
| Mental model | Document structure — the blocks and their cardinality |
| Source map | Vocabulary — the **complete, closed** list of keywords/types/fields |
| Canonical pattern | Minimal valid document |
| Extension points | Authoring method — how to make choices for a given input |
| Anti-patterns | Hard constraints — "do NOT violate" |
| Quick reference | Cheat-sheet — the whole grammar in one block |

Two rules specific to this variant:

1. **Declare the vocabulary closed.** State plainly that the file is the
   complete grammar and no keyword outside it may be invented. Without this an
   agent will extrapolate plausible-looking syntax.
2. **State the output contract up front** — emit only valid `<lang>`, nothing
   else; every output must parse.

`margaid/AGENTIC_USE.md` is the reference implementation of this variant.

---

## 6. Maintenance

AGENTIC_USE.md is **code-adjacent documentation**. Stale entries are worse than
missing ones: an agent trusts the file over the code and will confidently
generate against an API that no longer exists.

- Update it in the **same commit** as any change to a public signature, a
  required config field, an error message quoted in the file, or a source-map
  path.
- Add an anti-pattern whenever review catches a mistake the file would have
  prevented. This is the primary growth mechanism.
- **Check links in CI.** Relative paths drift silently during restructuring —
  pirn's root file currently points domain links at
  `packages/pirn-agents/src/pirn_agents/…`, but the files live at
  `packages/pirn-agents/pirn_agents/…`, so all six resolve to nothing.
- Periodically verify every code block still executes. A worked example is a
  test that has not been wired up.

---

## 7. Adoption checklist

For a new repository:

1. Write the level-0 file first. Thesis sentence, including the "does NOT" half.
2. Draft Mental model and Source map. If the source map will not fit one
   screen, decide the split now.
3. Write the Canonical pattern and **run it**.
4. Fill Anti-patterns from real observed mistakes. Ship with three rather than
   invent ten.
5. Write the Quick reference last — it is a summary, and summarising early
   locks in a structure you have not validated.
6. Add child files only where a sub-area's mental model genuinely diverges.
7. Add the child index, and a link check to CI.

Reference implementations: [AGENTIC_USE.md](AGENTIC_USE.md) (level 0, full
skeleton), [packages/pirn-signal/pirn_signal/AGENTIC_USE.md](packages/pirn-signal/pirn_signal/AGENTIC_USE.md)
(level 1), [packages/pirn-signal/pirn_signal/filters/AGENTIC_USE.md](packages/pirn-signal/pirn_signal/filters/AGENTIC_USE.md)
(level 2, core five only), [../margaid/AGENTIC_USE.md](../margaid/AGENTIC_USE.md)
(DSL variant).

---

*Format specification v1. Derived from 77 AGENTIC_USE.md files across pirn and margaid.*
