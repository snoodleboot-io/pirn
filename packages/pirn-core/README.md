# pirn-core

The core of **pirn** — a pipeline framework where everything is a *knot*. Imports as `pirn`.

`pirn-core` carries the engine, run/manager machinery, the connector public surface
(`pirn.connectors.*`), the shared provider bases (`pirn.core.providers.*`), and the
`sweet_tea` registry plumbing. Its base install is **domain-free** (constraint C2):
`import pirn` pulls no heavy backend, and core never imports a `pirn_<domain>` package.

## Install

```bash
pip install pirn-core
```

Backends are optional extras (none installed by default):

```bash
pip install "pirn-core[postgres,s3,kafka]"   # pick the backends you need
```

## Domains

The domain libraries ship as separate, independently-installable packages that each
depend on `pirn-core` and self-register their knots under `library="pirn"`:

| Package | Imports as | Domain |
|---|---|---|
| `pirn-signal` | `pirn_signal` | Digital signal processing |
| `pirn-data` | `pirn_data` | Data engineering / analytics |
| `pirn-ml` | `pirn_ml` | ML engineering (depends on `pirn-data`) |
| `pirn-agents` | `pirn_agents` | LLM agents |
| `pirn-health` | `pirn_health` | Health / clinical |
| `pirn-oilgas` | `pirn_oilgas` | Oil & gas |

Install a domain (it pulls `pirn-core` automatically):

```bash
pip install pirn-signal
```

See the [project README](https://github.com/snoodleboot-io/pirn) for the full
documentation, architecture, and the core/domains split rationale (ADR).
