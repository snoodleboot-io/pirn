# pirn examples

Each subdirectory is a self-contained example. Run any of them from the **repo root** with `uv run`.

---

## Explorer

```bash
uv run python examples/explore_pipelines.py
```

Scans every example in this folder, builds a graph of each tapestry's node topology, and generates a single self-contained HTML file (`pirn_explorer.html`) that opens in your browser. From there you can select any tapestry, browse its execution history, click a node to inspect its outcome and timing, and — for SubTapestry nodes — double-click to drill into the inner pipeline.

Run the individual examples first to populate the execution history, then open the explorer to see everything together.

You can also use the CLI directly:

```bash
pirn-explore examples/
pirn-explore examples/ --output my_explorer.html --no-open
```

> Requires an internet connection — D3 is loaded from CDN.

---

## data_pipeline

### simple_etl.py

```bash
uv run python examples/data_pipeline/simple_etl.py
```

The simplest possible real-world pipeline: read CSV data, clean it (drop bad rows, normalise types), enrich it (add derived columns), write to SQLite. There is nothing clever about the domain — the point is to see how pirn handles a linear chain of typed transformations.

The interesting bit is caching. Run it twice in a row and watch the second run skip every knot — the inputs haven't changed so the cached outputs are replayed. Then modify the source data and run again: only the knots downstream of the change re-execute. This is pirn's content-addressed cache in its most visible form.

### complex_analytics.py

```bash
uv run python examples/data_pipeline/complex_analytics.py
```

A daily business metrics pipeline that models the kind of workload a data engineering team actually runs: three independent data sources (orders, events, users) are ingested in parallel, joined into a unified snapshot, then aggregated along two independent dimensions (region and cohort) simultaneously, before being merged into a final report.

The topology is deliberately wide — multiple parallel fan-outs — to show that pirn dispatches independent knots concurrently without any extra configuration. It also runs the same tapestry across several simulated days to demonstrate how caching interacts with date-parameterised inputs: days with identical upstream data reuse cached aggregations.

---

## software_execution

### ci_pipeline.py

```bash
uv run python examples/software_execution/ci_pipeline.py
```

A CI/CD pipeline that mirrors what most teams already have in GitHub Actions or Jenkins, but expressed as a pirn tapestry: checkout, then lint and typecheck in parallel, then a suite of tests in parallel, then build, then deploy. The build knot will not execute if any test suite fails — pirn propagates the error and skips all downstream knots automatically, so you never need to write explicit gate logic.

The example runs the same tapestry for several different commits. Open it in the explorer and compare runs side by side — the outcome badges (✓ / ✗ / ⊘) on each node tell you exactly where each run diverged and which knots were skipped as a consequence.

### request_handler.py

```bash
uv run python examples/software_execution/request_handler.py
```

An HTTP request handler decomposed as a tapestry. Each stage — parse, authenticate, authorise, validate body, fetch user, fetch account, process, audit log, send notification — is its own knot. The fetch_user and fetch_account knots run in parallel; audit and notification fire in parallel after processing.

The most instructive scenario is the failing auth case. When `authenticate` raises, every downstream knot receives `None` and skips gracefully — no try/except scattered across the pipeline. The full lineage records exactly which knot failed and which were skipped as a result, giving you a complete audit trail for every request without writing any logging code.

---

## content_moderation

```bash
uv run python examples/content_moderation/run.py
```

This is the YAML loader example. The pipeline is declared entirely in `tapestry.yaml` — nodes, their types, their parent wiring, and the callable references that implement each step. `run.py` loads the YAML, creates the tapestry, and runs it against several test inputs.

The pipeline itself models a content moderation backend: normalise text, then extract four signals in parallel (language detection, profanity check, PII detection, toxicity scoring), classify the combined signals, make a policy decision (allow / warn / block), and write an audit record.

This example is the right starting point if you want to define pipelines in configuration rather than code — for example, if non-engineers need to adjust the topology, or if you want to version pipelines separately from the Python implementation.

---

## pipeline_composition

```bash
uv run python examples/pipeline_composition/sub_tapestry.py
```

Demonstrates `SubTapestry` — a knot whose execution body is itself a complete inner tapestry. The outer pipeline stays clean (three high-level nodes), while each node owns a fully independent inner execution graph with its own caching, versioning, and lineage.

The domain is order processing. `ValidateOrder` runs an inner pipeline of inventory check and payment authorisation. `FulfillOrder` runs an inner pipeline of packing and shipping. Both inner pipelines run against the same SQLite history store as the outer pipeline, so the explorer can navigate into them.

The example runs four scenarios: a happy path, a payment blocked by amount limit, an order with an unknown item, and a cached re-run of the happy path. Run it and then open the explorer — select a run, click `ValidateOrder` or `FulfillOrder`, and use the "Open inner pipeline" button to drill into the inner graph and inspect its knot-level outcomes.

**Using SubTapestry from YAML** — the inner pipeline logic stays in Python, but the outer topology can be declared in YAML by referencing the subclass by its dotted import path:

```yaml
nodes:
  - id: validate
    type: knot
    callable: examples.pipeline_composition.sub_tapestry.ValidateOrder
    parents:
      order: order
```

---

## llm_agent

```bash
uv run python examples/llm_agent/chatbot_pipeline.py
```

A production-style chatbot backend modelled as a pirn tapestry. Each stage of handling a conversation turn is its own knot: parse the message, then classify intent and extract entities in parallel (two LLM calls that do not depend on each other), retrieve context from a knowledge base, run a safety check in parallel with retrieval, generate a response once both context and safety results are available, then post-process and log the turn in parallel.

The LLM calls use a fake Anthropic client by default so the example runs without any API key or network access. To wire in the real SDK, replace `_fake_llm_call()` with an `anthropic.AsyncAnthropic` call and set `ANTHROPIC_API_KEY` in your environment.

The key thing this example illustrates is that pirn's dependency graph naturally encodes the latency-optimal execution order for an LLM pipeline — you do not have to manually orchestrate which calls can overlap. The lineage also gives you a full record of every turn: inputs, outputs, timing, and any errors, without writing any instrumentation code.
