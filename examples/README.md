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

### chatbot_pipeline.py

```bash
uv run python examples/llm_agent/chatbot_pipeline.py
```

A production-style chatbot backend modelled as a pirn tapestry. Each stage of handling a conversation turn is its own knot: parse the message, then classify intent and extract entities in parallel (two LLM calls that do not depend on each other), retrieve context from a knowledge base, run a safety check in parallel with retrieval, generate a response once both context and safety results are available, then post-process and log the turn in parallel.

The LLM calls use a fake Anthropic client by default so the example runs without any API key or network access. To wire in the real SDK, replace `_fake_llm_call()` with an `anthropic.AsyncAnthropic` call and set `ANTHROPIC_API_KEY` in your environment.

The key thing this example illustrates is that pirn's dependency graph naturally encodes the latency-optimal execution order for an LLM pipeline — you do not have to manually orchestrate which calls can overlap. The lineage also gives you a full record of every turn: inputs, outputs, timing, and any errors, without writing any instrumentation code.

### agent_loop.py

```bash
uv run python examples/llm_agent/agent_loop.py
```

An agentic session over multiple messages where the execution graph grows dynamically at runtime. There is no pre-planned loop structure — each `AgentPlanner` knot runs, decides what actions to take, and registers those knots directly into the running extensible tapestry using `get_current_store()`. Data flows through real parent edges; there is no shared mutable state blob.

The shape of one iteration:

```
AgentPlanner → action_0, action_1, ... (run concurrently)
             → Aggregator(all actions)
             → AgentDecider(results=aggregator, ctx=planner)
```

`AgentDecider` integrates the results, updates the immutable `SessionContext`, and either registers the next `AgentPlanner` (more work to do) or a `_SessionFinalizer` (session complete). The final output is always at the well-known knot id `session_complete`.

Three action types demonstrate different graph depths:
- `run_tool_call` / `run_mcp_call` — leaf knots; inspect timing and output directly
- `SubAgentRunner` — a `SubTapestry`; drill into it to see its own `prepare → execute` inner pipeline

Knot IDs use a message-content slug (`whats_the_weather__m1i1`) so you can immediately read what each planner was working on in the explorer. A random `run_seed` is picked each run, producing a structurally different graph every time.

This is the right starting point for modelling real agent workloads where the execution plan is unknown until runtime.

---

## document_analysis

```bash
uv run python examples/document_analysis/document_analysis.py
```

A document analysis pipeline that demonstrates subclassing `Knot` directly rather than using the `@knot` decorator. All processing nodes are class-based — typed, named, and composable through inheritance.

The pipeline runs four parallel analysis branches from a shared `TextNormaliser` output, then converges into a single `AnalysisReport`:

```
DocumentLoader ──► TextNormaliser ──┬──► SentimentScorer  ──┐
                                    ├──► ReadabilityScorer   ├──► AnalysisReport
                                    ├──► KeywordExtractor    │
                                    └──► TopicClassifier   ──┘
```

Key patterns shown:

- **Base class with shared helpers** — `_BaseAnalyser(Knot)` provides `_freq()`, `_tfidf()`, and `_avg_word_len()` used by all four analyser subclasses. Shared logic lives in the class, not repeated across `process()` methods.
- **Config injection via process() args** — `KeywordExtractor` declares `max_keywords: int` in its `process()` signature; passing `max_keywords=10` at construction time stores it as a config constant.
- **Pure class-level state** — `SentimentScorer` and `TopicClassifier` keep their lexicons and signal dictionaries as class attributes, shared across all instances.
- **Input validation in `process()`** — `DocumentLoader` trims and validates its inputs, raising `ValueError` on empty title or body.

Three sample articles (science, finance, health) are analysed in sequence against the same tapestry. Run it and open the explorer to see the parallel branch structure and per-knot timing.

---

## lab_batch

```bash
uv run python examples/lab_batch/lab_batch.py
```

A pathology lab receives batches of patient samples, each containing multiple individual samples. Every sample must be independently analysed against reference ranges for five biomarkers and a per-sample report generated, then all reports are aggregated into a batch summary.

The central concept here is the `Map` distribution marker — place it on a knot's input to fan the knot out over every element in the collection concurrently, without writing a loop or managing concurrency:

```python
analysed = analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
reports  = generate_report(analysed=Map(analysed), _config=KnotConfig(id="report"))
```

The knot appears in the graph and lineage as itself (`analyse_sample`, not `Map`). Its `process` method is typed for a single element; the engine handles the fan-out. Output is `list[T]`. Two batches are run (morning and afternoon), producing varied outcomes across both.

---

## financial

### fraud_detection.py

```bash
uv run python examples/financial/fraud_detection.py
```

A fraud pipeline that runs a required core risk analysis on every transaction, then enriches the decision with three supplementary signals — device fingerprinting, geolocation cross-reference, and a third-party fraud bureau lookup. Any of these optional sources can be absent or unavailable (rate limits, no device ID for mobile web, etc.) without stopping the pipeline.

This demonstrates `RECEIVE_ERRORS` error policy: the `decide` knot receives all its parents as `Result` objects rather than unwrapped values. It checks each optional signal with `isinstance(signal, Ok)` and uses the value only when it arrived. The five test transactions cover a range: clean approval, review cases, a mobile checkout with no device ID, a high-risk country transaction, and a blocked case. Open the explorer to see which nodes show `err` vs `skipped` vs `ok` across the runs.

### loan_underwriting.py

```bash
uv run python examples/financial/loan_underwriting.py
```

A loan application is risk-assessed, then routed to one of three underwriting tracks (prime / near-prime / subprime) based on credit score, debt-to-income ratio, and employment history. Each track runs its own approval logic and produces a decision. An `Aggregator` collects all three tracks — exactly one will be `Ok`, the other two `Skipped` — and merges them into a final decision record.

This is the `Branch` + `Aggregator` pattern: one result fans out into multiple possible flows, only one executes, and they converge back. The six test applications deliberately span all three tracks and include declines. In the explorer, the Branch node and its three outputs are visible in the graph — you can see `ok` on the selected track and `skipped` on the others for each run.
