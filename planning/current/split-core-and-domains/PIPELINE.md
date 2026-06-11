# Reusable Multiagent Execution Pipeline (shared core)

**Status:** Design — applies to every SCD phase plan in this directory.
**Owner:** orchestrator-agent. **Branch:** `feat/51-split-core-and-domains`.

> This is the **reusable core** referenced by every `EXECUTION_PIPELINE_PHASE*.md`. Those phase plans inherit Sections A–D below verbatim and only add their own **delta sections** (environment manifest, execution map, subagent specs, test strategy, integration verification, gap report). Read this once; each phase plan tells you only what changes.

---

## A. Conventions (loaded once, apply to every phase)

| Convention | Location | Governs |
|---|---|---|
| Core system + startup checklist | [.claude/conventions/core/general.md](../../../.claude/conventions/core/general.md) | branch check, session protocol, scope discipline |
| Python conventions | [.claude/conventions/languages/python.md](../../../.claude/conventions/languages/python.md) | absolute imports, **no re-export/forwarding**, `T \| None`, no constants (YAML/pydantic-settings), `__init__.py` everywhere, pyright strict, one-class-per-file = snake-case filename |
| Shared workflow | [.claude/workflows/feature.md](../../../.claude/workflows/feature.md) | restate → read-first → propose → confirm → implement → test → self-review |
| Agent registry (24 agents) | [CLAUDE.md](../../../CLAUDE.md) | one-agent-per-task routing |
| SCD planning package | [README.md](./README.md), [FEATURES.md](./FEATURES.md), [ADR.md](./ADR.md), [REVIEW.md](./REVIEW.md) | item specs, acceptance criteria, critical path |

**Standing convention notes (true every phase):**
- A class **rename** is always a **file rename** (`git mv`) — snake-case-filename rule.
- `core/general.md` carries `TODO` for error-handling/commit-style/PR-size — defer to python.md (typed exception hierarchy) + observed repo style (Conventional Commits, `pirn/exceptions`).
- No `pass` / `TODO` / `NotImplementedError` / placeholder returns in any delivered output. A genuine external blocker is *flagged*, never stubbed.

---

## B. Agent roster → pipeline roles (stable mapping)

| Pipeline role | Agent | Notes |
|---|---|---|
| PM / architect / gate decisions | architect-agent (+ plan, product) | owns ADR confirm/amend notes |
| Refactor (structural moves, renames, folds) | refactor-agent | the workhorse of Phases 1–3 |
| Code (new behavior: shim, helpers) | code-agent | Phase 4 (shim, `discover_installed_domains`) |
| ATDD + TDD | test-agent (two concurrent invocations) | acceptance vs unit/integration |
| Verify / integration | test-agent + debug-agent | aggregation |
| Enforce (standards audit) | enforcement-agent | gate G-ENF |
| Security | security-agent | gate G-SEC |
| Debug / retry | debug-agent | retry-loop owner |
| Environment / CI / infra | devops-agent | **owns Env-Setup gate** (no native env agent — substitution) |
| Migration (codemods) | migration-agent | Phase 4 import-rewrite |
| Review | review-agent | gate G-REV |
| Docs | document-agent | Phase 4/5 docs |
| Orchestration / aggregation / session | orchestrator-agent | top-level coordinator |

**Standing role gaps (true every phase):** no dedicated env-setup agent (→ devops-agent); ATDD/TDD share test-agent (→ split into 2 concurrent subagents).

---

## C. Standing pipeline shape

```
Env-Setup gate (HARD prereq, devops-agent)
  → fan-out parallel lanes (per-phase: spike / test-design / refactor subagents)
    → Aggregation (orchestrator: behavior suite + ruff + pyright + phase-specific assertion)
      → Sequential gates: G-ENF → G-SEC → G-REV
        → architect decision note (confirm/amend relevant ADR)
          → orchestrator updates session + posts AC checklist to the phase's issues
            → next phase unblocks
```

**Rules that hold every phase:**
- **Nothing unblocks until the Env-Setup gate is green** (services healthy + baseline captured).
- File-mutating subagents that run concurrently use **git-worktree isolation**; the aggregator merges.
- Gates are **sequential and blocking** — a red routes to the debug loop, never forward.
- Subagents receive: persona file + loaded conventions + task scope + shared-interface contract (inputs/outputs + explicit "do not touch" siblings where names collide across domains).

---

## D. Convention enforcement + debug/retry (stable)

**Enforcement checkpoints (same every phase):**

| Convention | Verified at |
|---|---|
| one-class/file, filename = snake(class) | G-ENF |
| absolute imports, no re-export | G-ENF + `ruff` in aggregation |
| `T \| None`, pyright strict, public type hints | aggregation `pyright` (zero new vs baseline) |
| no new constants (YAML/pydantic-settings) | G-ENF spot-check |
| typed exceptions, no silent swallow | G-REV |
| behavior preserved (refactors) | G-REV + full suite green |
| secret/DSN handling | G-SEC |
| session updated, AC tracked | orchestrator final step |

**Debug & retry (same every phase):**
- **Owner:** debug-agent, coordinated by orchestrator.
- **Retry scope, smallest blast radius first:** subagent-local → lane-level → env-level.
- **Budget:** 3 attempts per scope, each carrying a root-cause note (no blind re-runs).
- **Escalate to the human when:** retries exhausted; OR an ADR amendment is implied; OR a G-SEC finding; OR an environment blocker. Escalation **pauses all lanes and re-presents** (per the material-change rule).

---

## E. Phase plan index

| Plan | Items | Fidelity | Gate dependency |
|---|---|---|---|
| [EXECUTION_PIPELINE_SCD01.md](./EXECUTION_PIPELINE_SCD01.md) | SCD-01 | **full** | none — this *is* the gate |
| [EXECUTION_PIPELINE_PHASE0.md](./EXECUTION_PIPELINE_PHASE0.md) | SCD-02,03,04 | **full** | after SCD-01 |
| [EXECUTION_PIPELINE_PHASE1.md](./EXECUTION_PIPELINE_PHASE1.md) | SCD-05,06,07 | skeleton ⚠ | ADR-4 outcome |
| [EXECUTION_PIPELINE_PHASE2.md](./EXECUTION_PIPELINE_PHASE2.md) | SCD-08,09,10 | skeleton ⚠ | ADR-3 edges |
| [EXECUTION_PIPELINE_PHASE3.md](./EXECUTION_PIPELINE_PHASE3.md) | SCD-11–16 | skeleton ⚠ | extraction recipe (SCD-11) |
| [EXECUTION_PIPELINE_PHASE4.md](./EXECUTION_PIPELINE_PHASE4.md) | SCD-17–23 | skeleton ⚠ | all domains extracted |
| [EXECUTION_PIPELINE_PHASE5.md](./EXECUTION_PIPELINE_PHASE5.md) | SCD-24–29 | skeleton ⚠ | CI skeleton (SCD-04) |

`⚠` = item list / dependencies / env / lane shape / acceptance criteria are stable (from `FEATURES.md`); gate-dependent execution detail is marked provisional and re-presented before that phase runs.
