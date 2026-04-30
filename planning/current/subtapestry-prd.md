# PRD: SubTapestry Knot

**Status:** Complete  
**Author:** John Aven  
**Date:** 2026-04-30  
**Branch:** feat/subtapestry-knot

---

## 1. Problem Statement

pirn pipelines are flat graphs. Every knot lives in the same tapestry namespace, and there is no way to encapsulate a sub-pipeline as a single unit of work. This creates two pain points:

1. **Composition at scale.** Large pipelines become hard to reason about because all knots share a single flat namespace. There is no way to say "this chunk of the graph is one logical step."
2. **Reuse.** A pipeline that is useful on its own cannot be embedded inside a larger pipeline without copy-pasting its knots and rewiring them manually.

## 2. Goal

Introduce a `SubTapestry` knot: a knotless knot that wraps a complete inner tapestry and runs it as a single step in an outer pipeline. Its `Result` is determined by whether the inner pipeline run succeeds.

**"Knotless"** means: the user does not implement `process()`. The framework provides the execution logic. The user declares the inner tapestry and the data bindings.

## 3. User Story

> As a pipeline author, I want to embed a complete inner pipeline as a single node in my outer pipeline, so that I can compose reusable sub-pipelines without collapsing their knot namespaces.

```python
# Inner pipeline — a self-contained tapestry
with Tapestry() as inner:
    raw = FetchKnot(_config=KnotConfig(id="fetch"))
    cleaned = CleanKnot(data=raw, _config=KnotConfig(id="clean"))
    scored = ScoreKnot(data=cleaned, _config=KnotConfig(id="score"))

# Outer pipeline
with Tapestry() as outer:
    source = SourceKnot(_config=KnotConfig(id="source"))

    sub = SubTapestry(
        tapestry=inner,
        output="score",           # surface the "score" knot's value
        _config=KnotConfig(id="sub"),
    )

    sink = SinkKnot(result=sub, _config=KnotConfig(id="sink"))
```

---

## 4. Functional Requirements

### 4.1 Construction

| Requirement | Detail |
|-------------|--------|
| `tapestry` arg | A pre-built `Tapestry` instance. Required. |
| `output` arg | A knot id within the inner tapestry whose `Ok` value is surfaced as the SubTapestry's output. Optional. If omitted, the output is the inner `RunResult`. |
| `bind` arg | A `dict[str, Knot]` mapping inner parameter ids to outer parent knots. Outer parent values are injected into the inner run as parameter values. Optional. |
| `_config` arg | Standard `KnotConfig`. Required (consistent with all knots). |
| No `process()` | SubTapestry does not ask the user to implement `process()`. It is "knotless." |

### 4.2 Execution

| Requirement | Detail |
|-------------|--------|
| Runs inner pipeline | At execution time, SubTapestry calls `tapestry.run(RunRequest(...))` on the inner tapestry using its own `LocalDispatcher` (inheritable). |
| Parameter injection | Values from outer parents (resolved by the outer engine) are passed as `RunRequest.parameters` to the inner run, keyed by the inner parameter ids declared in `bind`. |
| Success → Ok | If the inner run succeeds (`run_result.succeeded`), SubTapestry returns `Ok(value)` where `value` is either the designated `output` knot's value or the full `RunResult`. |
| Failure → Err | If the inner run produces any exceptions, SubTapestry returns `Err` wrapping a synthetic `ExceptionRecord` that includes the inner run's exception records. |
| Skipped inner knots | Skipped inner knots do not constitute failure. Only `Err` outcomes in the inner run count as failure. |
| Lineage | The inner `RunResult` is stored in the outer `KnotLineage.extra["inner_run"]` for traceability. |

### 4.3 Isolation

| Requirement | Detail |
|-------------|--------|
| Separate run id | The inner run gets its own `run_id`, distinct from the outer run. |
| Separate history | The inner tapestry uses its own backends (store, history, data_store). The outer run does not write the inner knots' lineage to its own history. |
| No namespace collision | Inner knot ids do not appear in the outer tapestry's namespace. |

### 4.4 The `output` knot

- If `output` is specified, the named knot must exist in the inner tapestry. Validated at construction time.
- If the named knot was skipped or errored in the inner run, SubTapestry returns `Err` (not `Ok(None)`).
- If `output` is omitted, `Ok(RunResult)` is returned on success.

---

## 5. Non-Goals

- SubTapestry does not propagate the outer dispatcher into the inner run (the inner tapestry uses its own configured dispatcher).
- SubTapestry does not support mid-run registration (`extensible=True`) for the inner run in this iteration.
- SubTapestry does not expose inner knots to the outer shed's topological sort — the inner graph is fully opaque to the outer engine.
- SubTapestry does not stream inner status events to the outer emitters (inner emitters remain scoped to the inner tapestry).

---

## 6. Out-of-Scope / Future Work

- Nested SubTapestry (SubTapestry inside SubTapestry) — works automatically since a SubTapestry is just a Knot.
- Passing outer `RunRequest` context (actor, trigger, environment) into the inner run — could be a future option.
- `@subtapestry` decorator analogous to `@knot`.

---

## 7. Success Criteria

1. A SubTapestry knot can be constructed, registered in an outer tapestry, and run without error.
2. Outer parent values are correctly injected into inner parameter knots.
3. Inner pipeline success → outer `Ok`.
4. Any inner pipeline `Err` → outer `Err`.
5. Inner run id and lineage are separate from the outer run.
6. The designated `output` knot's value (or full `RunResult`) is surfaced correctly.
7. Unit tests cover: success, inner failure, parameter injection, output knot selection, missing output knot.
