# Session handoff — pirn `feat/domain-knot-libraries`

Compact status for a fresh session / model picking up this branch.

## TL;DR

- Branch `feat/domain-knot-libraries` is **33 commits** ahead of main on PR [#13](https://github.com/snoodleboot-io/pirn/pull/13) (draft).
- Suite: **3834 passing, 58 skipped, 0 failing**.
- Phase 4 (file formats) is **complete** — all 118 format items checked.
- AGENTIC_USE.md for root + all 6 domains is done and committed.
- Branch is ready for PR review / merge planning.

## Where the work lives

| Doc | Purpose |
|-----|---------|
| `planning/current/phase4-progress.md` | Phase 4 checklist (all complete) |
| `planning/current/phase4-data-formats-prd.md` | Phase 4 design + wave plan |
| `planning/current/execution-plan.md` | Original Phase 1–3 execution plan |
| `planning/current/sweet_tea_change_request.md` | Upstream cache bug filed against sweet_tea |
| `planning/current/domain-knot-libraries-ard.md` | Domain knot library ARD |
| `planning/current/domain-knot-libraries-prd.md` | Domain knot library PRD |
| `AGENTIC_USE.md` | Framework agentic use guide (links to all domain guides) |

## What was done this branch

- Phase 1–3: connectors, capability interfaces, security hardening, convention cleanup
- Phase 4: 98+ file format connectors across all 6 domains (~900 tests)
- Framework coercion: `Knot | T` scalar auto-wrapping via `__init_subclass__`
- `@tool` decorator: converts plain functions to `Tool` instances (`pirn[agents]`)
- Control knot renames: `*Gate` → `*Check` for agent control knots
- Full Google-style docstrings on all `process()` methods
- AGENTIC_USE.md: root + agents, data, ml, health, signal, oilgas domain guides

## Archived planning docs

See `planning/archive/` for:
- subtapestry-ard/prd (Complete)
- map-redesign-ard (Accepted/implemented)
- phase3-review-2026-05-01 (all findings resolved)
- security-review-2026-05-01 (zero open findings)
- enforcement-review-phase4-formats (resolved)

## Known open items

- `planning/current/sweet_tea_change_request.md` — upstream cache bug in
  `sweet_tea.registry.Registry`; workaround in place, fix needs to land
  in sweet_tea separately.
- CI wiring for `cyclonedx-bom` SBOM generation (deployment-specific,
  not blocking merge).
