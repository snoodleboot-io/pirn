# CI pipelines

The split workspace is driven by three GitHub Actions workflows. All three are
currently `workflow_dispatch`-only (frozen during the migration); PR / main /
nightly triggers re-enable together at the end of the split.

- [`workspace.yml`](../../.github/workflows/workspace.yml) — per-package lint / type / test / isolation / gates (SCD-24, 25, 26, 27)
- [`mutation.yml`](../../.github/workflows/mutation.yml) — per-package mutation testing (SCD-26)
- [`publish.yml`](../../.github/workflows/publish.yml) — lockstep build + publish + verify (SCD-28)

## `workspace.yml` — per-package matrix

Every job hangs off `changes` with `if: any == 'true'`, so an untouched package
spawns zero jobs.

```mermaid
flowchart TD
    PR([PR / main push]):::trig --> CH

    CH["changes<br/>dependency-aware closure<br/>→ affected packages (JSON)"]:::gate
    WR["workspace-resolve<br/>single uv.lock"]:::ind

    CH -->|"any == true"| LINT["lint · matrix: affected pkgs<br/>ruff + pyright (py3.12)"]:::job
    LINT --> TEST["test · matrix: pkg × py3.11–3.14<br/>pytest + per-pkg coverage → Codecov"]:::job
    CH --> ISO["install-isolation · matrix: affected<br/>clean venv → dep-tree closure<br/>+ no-backend + extras import"]:::job
    CH --> UNI["unified<br/>all pkgs installed → -m cross_domain<br/>registry parity / shim / rewriter"]:::job
    CH --> IG["import-graph<br/>C1 acyclic · C2 sink · C3 sole edge"]:::job
    CH --> VL["version-lockstep<br/>C4 floor + equal versions"]:::job

    classDef trig fill:#1f2937,color:#fff,stroke:#111;
    classDef gate fill:#b45309,color:#fff,stroke:#7c2d12;
    classDef job fill:#1e3a8a,color:#fff,stroke:#1e293b;
    classDef ind fill:#374151,color:#fff,stroke:#111;
```

### Dependency-aware change detection

A package runs if its own files, an **upstream `pirn` dependency**, or a
shared-root file changed.

```mermaid
flowchart LR
    subgraph diff["a changed file..."]
        F1["packages/pirn-signal/**"]
        F2["packages/pirn-data/**"]
        F3["packages/pirn-core/**"]
        F4["pytest.ini / uv.lock / .github/ (shared root)"]
    end

    F1 --> Rsig[signal]
    F2 --> Rdata[data] --> Rml[ml]
    F3 --> CORE[core]
    CORE --> Rsig & Rdata & Rml & Ra[agents] & Rh[health] & Ro[oilgas]
    F4 --> ALL["ALL 7 packages"]

    classDef d fill:#0f766e,color:#fff,stroke:#134e4a;
    class Rsig,Rdata,Rml,Ra,Rh,Ro,CORE,ALL d;
```

Worked examples: `signal/**` → `[signal]` · `data/**` → `[data, ml]` ·
`core/**` or any shared root → `[all 7]`.

## `publish.yml` — N-wheel build + publish (frozen, human-gated)

```mermaid
flowchart TD
    D([workflow_dispatch]):::trig --> B

    B["build<br/>calculate_version (anchor: pirn-core)<br/>→ stamp all packages (SCD-27)<br/>→ uv build --all-packages → wheels → artifact"]:::job

    B -->|"PR → testpypi"| TP["publish-testpypi<br/>env: testpypi · OIDC trusted publishing"]:::job
    B -->|"main → pypi"| PP["publish-pypi<br/>env: pypi · required reviewer (P5-B)"]:::stop
    TP --> V["verify · matrix: 7 pkgs<br/>install FROM INDEX → closure<br/>+ import + tapestry-check"]:::job

    classDef trig fill:#1f2937,color:#fff,stroke:#111;
    classDef job fill:#1e3a8a,color:#fff,stroke:#1e293b;
    classDef stop fill:#991b1b,color:#fff,stroke:#7f1d1d;
```

## `mutation.yml` — per-package mutation

```mermaid
flowchart TD
    T([PR / nightly / dispatch]):::trig --> M["matrix<br/>resolve pkg list (all 7 or override)"]:::gate
    M -->|pull_request| MPR["mutation-pr · matrix: pkgs<br/>mutmut changed files<br/>runner: pytest packages/&lt;pkg&gt;/tests"]:::job
    M -->|schedule / dispatch| MN["mutation-nightly · matrix: pkgs<br/>mutmut full tree + kill-rate"]:::job

    classDef trig fill:#1f2937,color:#fff,stroke:#111;
    classDef job fill:#1e3a8a,color:#fff,stroke:#1e293b;
    classDef gate fill:#b45309,color:#fff,stroke:#7c2d12;
```
