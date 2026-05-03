# Skill: Create AGENTIC_USE.md

Generate an `AGENTIC_USE.md` file for a library so that an AI agent can use it
correctly without reverse-engineering intent from source code.

---

## When to invoke

Use this skill when:
- You are about to use a library you are not confident about
- Scanning the library's source or API docs alone would not tell you the
  intended usage pattern
- You want to produce a reusable reference for future agents working with
  the same library

---

## Inputs

You need the following before starting:

| Input | How to get it |
|-------|---------------|
| Library name and version | From `pyproject.toml`, `requirements.txt`, or the user |
| Official documentation URL | Search or ask the user |
| Source repository URL | PyPI page, GitHub, or ask the user |
| The specific use-case context | What problem are you solving with this library? |

---

## Process

### Step 1 — Understand the library's mental model

Before reading any API, answer these questions:

1. What category of problem does this library solve?
2. What is the core abstraction (the thing you always create first)?
3. What does a minimal working program look like end-to-end?
4. Is there a lifecycle (create → configure → run → teardown)?

Sources to read, in priority order:
- Official "Getting Started" or "Quickstart" page
- The README introduction (first 20% only)
- One canonical example from the official examples directory
- The library's own `__init__.py` to see what it exports at the top level

Do NOT read:
- Full API reference pages (too much noise before you have the model)
- Advanced guides before the basics are clear
- Source implementation files (you want intent, not mechanics)

### Step 2 — Build the source map

Produce a curated tree of the library's public surface. This is NOT `find . -type f` — it is an annotated map of where to go and where not to go.

Rules:
- Include only the top two levels of the package tree
- Annotate every entry with one of: `← import from here`, `← extend from here`,
  `← DO NOT import (private)`, or `← built-in implementations (reference only)`
- If a directory contains only one relevant file, collapse it to that file
- Mark anything prefixed `_` as off-limits unless it is explicitly exported in `__init__.py`

Example output:

```
{library}/
├── __init__.py          ← everything the public API exports
├── core/
│   ├── base.py          ← Foo, Bar — base classes to extend
│   └── config.py        ← FooConfig — pass to constructors
├── providers/           ← built-in implementations (use or reference, do not extend)
├── utils/               ← public helpers, safe to import
└── _internal/           ← DO NOT import — private, may change without notice
```

### Step 3 — Identify the intended pattern

Find the single pattern the library authors expect for the 80% use case.
Look for:
- A builder or factory function that creates the main object
- A context manager (`with` block) if one exists
- The sequence of method calls that every example follows
- Config objects vs runtime arguments — which is which

Write this as one minimal code block. No error handling, no edge cases.
Just the skeleton that every real use will follow.

### Step 3 — Find the anti-patterns

This is the most important step. Look for:
- GitHub issues titled "I tried X but it didn't work"
- FAQ sections in docs
- Methods or classes that look useful but are marked internal or deprecated
- Things that work but bypass the intended mechanism (e.g. calling internal
  methods, constructing objects the library expects to build for you)
- Common mistakes in StackOverflow questions about this library

For each anti-pattern, write: what it looks like, why it seems right, and
what to do instead.

### Step 4 — Document extension points

Find where the library expects user-supplied code:
- Abstract base classes or interfaces to implement
- Callback signatures
- Configuration hooks
- Plugin/registry systems

For each, write the minimal implementation contract: what methods are
required, what they must return, what they must not do.

### Step 5 — Capture constraints and gotchas

Things that are not obvious from the API but will cause silent failures or
hard-to-debug errors:
- Ordering requirements (must call A before B)
- Thread-safety limitations
- Objects that must be closed or released
- Values that look optional but are effectively required
- Behaviour differences between sync and async paths

### Step 6 — Write two worked examples

Example 1: The canonical 80% case — the most common real-world use.
Example 2: One non-obvious variant that exercises an extension point or
           handles a constraint from Step 5.

Both examples must be complete and runnable. Comments only where the code
would otherwise be misleading.

---

## Output format

Write the file as `AGENTIC_USE.md` at the root of the project (or wherever
the user specifies). Use this structure exactly:

```markdown
# AGENTIC_USE — {Library Name} {version}

> One sentence: what this library does and what it does NOT do.

---

## Mental model

{One to three paragraphs. Explain the core abstraction and lifecycle.
No code yet. This section must be readable without seeing the API.}

---

## Source map

\```
{library}/
├── __init__.py          ← import from here
├── {module}/
│   ├── {file}.py        ← extend from here: ClassName, ClassName2
│   └── {file}.py        ← import from here: HelperClass
└── _{internal}/         ← DO NOT import — private API
\```

---

## Canonical pattern

{The minimal skeleton every usage follows. Code block only, with inline
comments on non-obvious lines. No error handling.}

---

## Extension points

{For each interface/hook the user must implement:}

### {InterfaceName}

**Contract:** {what methods are required and what they must return}
**Must not:** {things the implementation must avoid}

\```python
{minimal compliant implementation}
\```

---

## Anti-patterns

### {Anti-pattern name}

**Looks right because:** {why an agent would try this}
**Wrong because:** {what actually goes wrong}
**Do instead:** {correct approach, one code snippet if needed}

---

## Constraints and gotchas

- {constraint}: {consequence if violated}
- {gotcha}: {what goes wrong and how to avoid it}

---

## Worked examples

### Example 1 — {name of 80% case}

\```python
{complete runnable example}
\```

### Example 2 — {name of non-obvious variant}

\```python
{complete runnable example}
\```

---

## Quick reference

| Task | Call |
|------|------|
| {common task} | `{the right call}` |

---

*Generated for agent use. Covers version {version}. Check release notes
for breaking changes if using a newer version.*
```

---

## Quality checklist

Before saving the file, verify:

- [ ] The mental model section can be read without looking at any code
- [ ] The source map annotates every entry — no unannotated lines
- [ ] The source map marks all `_private` modules as off-limits
- [ ] The canonical pattern is the shortest possible working skeleton
- [ ] Every anti-pattern has a "do instead" that is demonstrably correct
- [ ] Extension point contracts specify what to return, not just what exists
- [ ] Constraints say what breaks, not just what the rule is
- [ ] Both worked examples run without modification
- [ ] No section duplicates information already in another section
- [ ] The file is under 500 lines — if longer, you have included too much

---

## Notes for the agent

- Prefer official documentation over inferred behaviour from source code.
  If docs and source conflict, note the conflict explicitly.
- If you cannot find the answer to a step, write `TODO: verify` rather than
  guessing. A known gap is better than confident misinformation.
- This file is read by agents before they write code. Optimise for
  unambiguous instructions, not for completeness. When in doubt, leave it
  out and add a `TODO: verify` note.
- Keep code examples in the library's idiomatic style. Do not apply project
  conventions that the library would not expect.
