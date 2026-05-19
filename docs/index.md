<div id="hero" class="pirn-hero">
<img src="pirn_logo.png" alt="pirn" class="pirn-hero-logo">
<h1>pirn</h1>
<p class="pirn-tagline">A pipeline framework where everything is a knot.</p>
</div>

pirn builds typed, async, observable computation pipelines. You declare *knots* — async functions with explicit dependency wiring — inside a *tapestry*, run the whole graph, and receive back a structured result including content-addressed lineage records that join across runs. Every value that flows through a pipeline is identified by a stable `sha256` hash, so two runs that produce identical outputs share the same hash with no extra infrastructure. Backends are protocols: swap SQLite for Postgres, local disk for S3, or a thread pool for a Dask cluster, without touching pipeline code.

---

<div class="pirn-feature-grid">

<div class="pirn-feature-card">
<h3>Tapestry</h3>
<p>Context-manager workspace that auto-registers knots and drives execution. Wire knots by passing one as a kwarg to another — no separate DAG API.</p>
</div>

<div class="pirn-feature-card">
<h3>Lineage</h3>
<p>Every run produces content-addressed <code>KnotLineage</code> records. Join across runs by output hash. Scrub values for GDPR without losing the lineage graph.</p>
</div>

<div class="pirn-feature-card">
<h3>Dispatchers</h3>
<p>Local, thread pool, Celery, Dask, or Ray — all behind the same protocol. Switch at construction time with no pipeline changes.</p>
</div>

<div class="pirn-feature-card">
<h3>YAML Pipelines</h3>
<p>Declare pipelines in YAML and load with <code>load_pipeline()</code>. Strict mode keeps callable resolution safe. Loose mode enables dynamic imports for trusted YAML.</p>
</div>

<div class="pirn-feature-card">
<h3>Visualization</h3>
<p>Render tapestries as Mermaid graphs or self-contained HTML. Explore all pipelines and their run history with the <code>pirn-explore</code> CLI.</p>
</div>

<div class="pirn-feature-card">
<h3>Streaming</h3>
<p>Feed continuous data into long-running pipelines with <code>IterableSource</code>, <code>FileTailSource</code>, or <code>KafkaStreamingSource</code>. Drive trigger-based pipelines from any stream.</p>
</div>

</div>

---

## Getting started

Install pirn (Python 3.11+ required):

```bash
pip install pirn
```

Install optional extras for production backends:

```bash
pip install pirn[sqlite]    # SQLiteStore + SQLiteHistory
pip install pirn[postgres]  # PostgresStore + PostgresHistory
pip install pirn[duckdb]    # DuckDBHistory — OLAP lineage queries
pip install pirn[s3]        # S3DataStore
pip install pirn[valkey]    # ValKeyStore + ValKeyDataStore
pip install pirn[otel]      # OpenTelemetry emitter
pip install pirn[all]       # everything
```

### Hello World

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest


@knot
async def double(x: int) -> int:  # (1)
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


async def main():
    with Tapestry() as t:                             # (2)
        x = Parameter("x", int)                      # (3)
        d = double(x=x, _config=KnotConfig(id="d"))  # (4)
        answer = add(a=x, b=d, _config=KnotConfig(id="answer"))

    result = await t.run(RunRequest(parameters={"x": 5}))  # (5)
    print(result.outputs)
    # {'param:x': 5, 'd': 10, 'answer': 15}


asyncio.run(main())
```

1. `@knot` wraps any async (or sync) function into a reusable knot class.
2. `with Tapestry() as t:` opens a registration context — knots built inside auto-register.
3. `Parameter` is a special knot that binds an external value at run time.
4. Passing `x` (a knot) as a kwarg makes `double` depend on `x`. The id is required — auto-generated ids make lineage records unreadable.
5. `run()` is async. The `RunRequest` carries parameter values.

The result carries `outputs` (raw values for each `Ok` knot), `lineage` (one `KnotLineage` per knot), and `exceptions` (any `Err` records).

---

## Key links

<div class="pirn-feature-grid">

<div class="pirn-feature-card">
<h3><a href="getting-started/quickstart/">Quickstart</a></h3>
<p>Installation, Hello World, reading results and lineage — step by step.</p>
</div>

<div class="pirn-feature-card">
<h3><a href="getting-started/concepts/">Concepts</a></h3>
<p>Glossary of every pirn term: Knot, Tapestry, Shed, Lineage, Thread, Loom, and more.</p>
</div>

<div class="pirn-feature-card">
<h3><a href="architecture/overview/">Architecture</a></h3>
<p>Three-layer model, execution wave loop, backend matrix, Mermaid component diagrams.</p>
</div>

<div class="pirn-feature-card">
<h3><a href="guides/backends/">Backends</a></h3>
<p>Capability matrix and decision tree for choosing storage backends.</p>
</div>

<div class="pirn-feature-card">
<h3><a href="guides/visualization/">Visualization</a></h3>
<p>pirn-explore CLI, Mermaid and HTML export, the 7W provenance panel.</p>
</div>

<div class="pirn-feature-card">
<h3><a href="cookbook/fan-out/">Cookbook</a></h3>
<p>Fan-out with Map, branching, streaming sources, testing patterns.</p>
</div>

</div>
