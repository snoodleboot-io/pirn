# Versioning & compatibility

pirn ships as eight independently-installable distributions — `pirn-core` plus the
six domains (`pirn-signal`, `pirn-data`, `pirn-ml`, `pirn-agents`, `pirn-health`,
`pirn-oilgas`). This page is the contract for how they are versioned relative to
one another (ADR-6 / SCD-27, SCD-29).

## Two phases

### 1. Lockstep — through the migration, up to 1.0

While the core/domains split stabilises, **every package shares one version** and
is released together. A single version bump stamps all eight `pyproject.toml`
files identically, and every inter-package dependency pins the same floor with an
ADR-6 upper bound:

```toml
# in each domain package, while MAJOR is 0:
dependencies = ["pirn-core>=0.4.0,<0.5.0"]   # pirn-ml additionally pins pirn-data
```

- **One bump, all eight.** [`scripts/stamp_workspace_version.py --version X.Y.Z`](../../scripts/stamp_workspace_version.py)
  writes the version and rewrites every `pirn-*` pin.
- **Upper bound (ADR-6).** While `MAJOR == 0` the **minor** is the breaking axis,
  so `0.4.0` caps at `<0.5.0`. From `1.0` onward the cap is the next **major**
  (`1.2.0` → `<2.0.0`).
- **Enforced in CI (constraint C4).** The `version-lockstep` gate runs
  `stamp_workspace_version.py --check` on every change: it fails unless all eight
  versions are equal **and** every inter-package pin floors at that version with
  the correct cap.

### 2. The 1.0 release — coordinated, breaking

`1.0` is a **single coordinated lockstep release** of all eight packages. It is the
point at which the deprecation window closes: the `pirn.domains.*` compatibility
shim is removed (ADR-5), and `import pirn.domains.<x>` stops working — consumers
must use `import pirn_<x>` (run [`pirn-migrate-imports`](migrating-to-split-packages.md)).
Because it is breaking for every package, all eight bump to `1.0.0` together.

### 3. Independent semver — after 1.0

Once the surface has settled, packages **may version independently**. A domain
that adds features bumps its own minor without forcing a workspace-wide release.
The coupling is then expressed purely through the dependency floor:

- Each domain declares a **minimum `pirn-core`** it requires (the first core
  version providing the symbols it uses — constraint C4) and a compatible upper
  bound (`<next-major-of-core`).
- `pirn-ml` additionally declares a minimum `pirn-data`.
- The lockstep stamper is no longer the release driver; the **C4 floor check**
  remains the enforcement mechanism — a pin must never floor *below* the core
  version that introduced a symbol the package depends on.

## Compatibility matrix

After 1.0, the supported combinations are published as a matrix (domain version ×
minimum `pirn-core`). Template:

| Package | Version | Requires `pirn-core` | Requires `pirn-data` | Notes |
|---|---|---|---|---|
| `pirn-core` | 1.x | — | — | the floor every domain pins against |
| `pirn-signal` | 1.x | `>=1.0,<2.0` | — | |
| `pirn-data` | 1.x | `>=1.0,<2.0` | — | |
| `pirn-ml` | 1.x | `>=1.0,<2.0` | `>=1.0,<2.0` | sole retained domain edge (ADR-3) |
| `pirn-agents` | 1.x | `>=1.0,<2.0` | — | |
| `pirn-health` | 1.x | `>=1.0,<2.0` | — | |
| `pirn-oilgas` | 1.x | `>=1.0,<2.0` | — | |

During the lockstep phase this table is trivial — every row is the same version —
so it is only **maintained as a published artifact from 1.0 onward**, when the
versions diverge.

## Why floors, not exact pins

Pinning a floor (`>=`) rather than an exact version lets a consumer pick up
`pirn-core` bug-fixes without a domain re-release, while the upper bound prevents
a breaking core from silently satisfying the requirement. Constraint **C4** — *a
package must pin `>=` the core version that introduced the symbols it uses* — is
what keeps that floor honest, and is checked in CI for every package.
