# Branching Pipelines

pirn has two mechanisms for conditional execution: `Branch` (routes to one of N named paths based on a selector) and `Gate` (passes through or skips based on a predicate).

---

## Branch: routing to one of N paths

`Branch` takes one input and a selector function. The selector returns the name of the branch to activate. All other branches produce `Skipped`.

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, knot, RunRequest, Branch


@knot
async def classify_message(text: str) -> dict:
    """Classify a message into a type."""
    if text.startswith("/"):
        return {"type": "command", "payload": text[1:]}
    elif "?" in text:
        return {"type": "question", "payload": text}
    else:
        return {"type": "statement", "payload": text}


@knot
async def handle_command(msg: dict) -> str:
    return f"Executing command: {msg['payload']}"


@knot
async def handle_question(msg: dict) -> str:
    return f"Answering question: {msg['payload']}"


@knot
async def handle_statement(msg: dict) -> str:
    return f"Acknowledging: {msg['payload']}"


def message_type_selector(msg: dict) -> str:
    return msg["type"]   # returns one of "command", "question", "statement"


async def main():
    with Tapestry() as t:
        text = Parameter("text", str)

        classified = classify_message(
            text=text,
            _config=KnotConfig(id="classified"),
        )

        route = Branch(
            input=classified,                      # (1) value to branch on
            selector=message_type_selector,        # (2) callable returning branch name
            branches=("command", "question", "statement"),  # (3) valid branch names
            _config=KnotConfig(id="route"),
        )

        # Access individual branch outputs using subscript notation
        cmd_result = handle_command(
            msg=route["command"],                  # (4) only activated on "command"
            _config=KnotConfig(id="cmd_result"),
        )
        q_result = handle_question(
            msg=route["question"],
            _config=KnotConfig(id="q_result"),
        )
        stmt_result = handle_statement(
            msg=route["statement"],
            _config=KnotConfig(id="stmt_result"),
        )

    result = await t.run(RunRequest(parameters={"text": "/help"}))

    lineage = {rec.knot_id: rec for rec in result.lineage}
    print(lineage["cmd_result"].outcome)    # "ok"
    print(lineage["q_result"].outcome)     # "skipped"
    print(lineage["stmt_result"].outcome)  # "skipped"
    print(result.outputs["cmd_result"])    # "Executing command: help"


asyncio.run(main())
```

1. `input=classified` — the knot whose output is passed to the selector.
2. `selector=message_type_selector` — callable `(value) -> str`. The returned string must be one of the declared branch names.
3. `branches=(...)` — tuple of valid branch names. Any name not in this tuple will raise at construction time.
4. `route["command"]` — subscript access to a specific branch output. This is a `BranchOutput` object that acts as a parent knot, producing `Skipped` when the branch was not selected.

---

## Gate: pass-through or skip

`Gate` takes one input and a predicate. If the predicate returns `True`, downstream knots receive the value. If `False`, they receive `Skipped`.

```python
from pirn import Gate


@knot
async def compute_score(text: str) -> float:
    return len(text) / 100.0


@knot
async def publish_high_score(score: float) -> dict:
    return {"published": True, "score": score}


async def main():
    with Tapestry() as t:
        text = Parameter("text", str)

        score = compute_score(
            text=text,
            _config=KnotConfig(id="score"),
        )

        quality_gate = Gate(
            input=score,
            predicate=lambda s: s > 0.5,   # pass through if score > 0.5
            _config=KnotConfig(id="quality_gate"),
        )

        published = publish_high_score(
            score=quality_gate,             # skipped if gate is closed
            _config=KnotConfig(id="published"),
        )

    result = await t.run(RunRequest(parameters={"text": "short"}))
    print(result.lineage[-1].outcome)   # "skipped" (too short)

    result2 = await t.run(RunRequest(parameters={
        "text": "a" * 60  # long enough to score > 0.5
    }))
    print(result2.lineage[-1].outcome)  # "ok"


asyncio.run(main())
```

---

## Handling all branches with an Aggregator

To collect results from all branches (regardless of which was activated), use an `Aggregator` with `RECEIVE_ERRORS`:

```python
from pirn import Aggregator, ErrorPolicy, KnotConfig


merged = Aggregator(
    parents={
        "command": cmd_result,
        "question": q_result,
        "statement": stmt_result,
    },
    combine=lambda results: next(
        (r for r in results.values() if not isinstance(r, (str,)) or r),
        None
    ),
    _config=KnotConfig(
        id="merged",
        error_policy=ErrorPolicy.RECEIVE_ERRORS,
    ),
)
```

A simpler pattern is a single `Sink` that uses `RECEIVE_ERRORS`:

```python
from pirn import Sink, ErrorPolicy, KnotConfig
from pirn.core.result import Result


class AuditSink(Sink):
    async def process(
        self,
        cmd: Result[str],
        question: Result[str],
        statement: Result[str],
    ) -> None:
        outcome = next(
            r.value for r in [cmd, question, statement] if r.is_ok
        )
        print(f"Handled: {outcome}")


audit = AuditSink(
    cmd=cmd_result,
    question=q_result,
    statement=stmt_result,
    _config=KnotConfig(id="audit", error_policy=ErrorPolicy.RECEIVE_ERRORS),
)
```

---

## Branch in YAML

```yaml
name: message_router

nodes:
  - id: text
    type: parameter
    type_: str

  - id: classified
    type: knot
    callable: classify_message
    parents:
      text: text

  - id: route
    type: branch
    input: classified
    selector: message_type_selector
    branches:
      - command
      - question
      - statement

  - id: cmd_result
    type: knot
    callable: handle_command
    parents:
      msg: route.command        # branch output subscript in YAML

  - id: q_result
    type: knot
    callable: handle_question
    parents:
      msg: route.question
```

---

**See also:** [Nodes — Branch](../api/nodes.md#branch), [Nodes — Gate](../api/nodes.md#gate), [Error Handling](../guides/error-handling.md)
