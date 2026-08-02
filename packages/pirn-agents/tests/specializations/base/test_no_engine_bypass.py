"""Guard: a pattern pipeline's ``process()`` must build a graph, not do the work.

A `SubTapestry` promises the engine's guarantees — a `Result` per knot, run
history, lineage, determinism, replay. It delivers them only if `process()`
*declares an inner graph and returns its sink*. A `process()` that computes the
answer in Python and hands back a knot wrapping the finished value satisfies the
type signature and delivers none of it.

The two shapes are indistinguishable by inspection, which is the actual problem:
"build a pipeline" means two different things depending on which file you opened.
See PIR-731.

`SubTapestry.__call__` already enforces the easy half at runtime — the sink must
be a `Knot`, and must be registered in the inner tapestry. That check cannot see
the bypass, because a closure over a precomputed value *is* a registered `Knot`.
These three static checks cover what it cannot.

## Why this is a ratchet, not a clean assertion

There are 14 pipelines bypassing the engine today. Fixing them is a per-pipeline
design job — WS7 did five and each needed its own decision — so the honest guard
is one that freezes the inventory rather than pretending it is empty.

The allowlists are asserted by **exact equality**, deliberately:

* adding a bypass fails, because the finding is not in the list;
* fixing one *without* updating the list also fails, because the list still
  names it.

The second half is what keeps the list from rotting into a lie. When you fix a
pipeline, delete its line and watch this test go green.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import unittest
from pathlib import Path

from pirn.nodes.sub_tapestry import SubTapestry

import pirn_agents.specializations as _specializations_pkg

# --- known bypasses, frozen ------------------------------------------------

#: `await <child>.process(...)` — runs a child pipeline's body directly instead
#: of wiring it as a knot, so the child contributes no Result and no lineage.
#: PIR-769 fixed four of these in multi_agent/; these are what remain.
AWAITS_CHILD_PROCESS = frozenset(
    {
        "lats/lats_search.py::LatsSearch",
        "plan_react/plan_react_pipeline.py::PlanReActPipeline",
        "reflexion/reflexion_pipeline.py::ReflexionPipeline",
    }
)

#: Returns a `Source` defined inside `process()` that closes over an
#: already-computed value. The engine then "runs" a graph of one knot whose job
#: is to hand back an answer Python already had.
RETURNS_INLINE_SOURCE = frozenset(
    {
        "lats/lats_search.py::LatsSearch",
        "multi_agent/orchestrator_agent.py::OrchestratorAgent",
        "multi_agent/orchestrator_workers.py::OrchestratorWorkers",
        "plan_react/plan_react_pipeline.py::PlanReActPipeline",
        "prompt_chaining/prompt_chain_pipeline.py::PromptChainPipeline",
        "rag/agentic_rag_pipeline.py::AgenticRagPipeline",
        "rag/flare_active_rag_pipeline.py::FlareActiveRagPipeline",
        "rag/multi_hop_rag_pipeline.py::MultiHopRAGPipeline",
        "reflexion/reflexion_pipeline.py::ReflexionPipeline",
        "self_ask/self_ask_pipeline.py::SelfAskPipeline",
        "structured_output/json_extractor_pipeline.py::JsonExtractorPipeline",
        "structured_output/pydantic_validator_pipeline.py::PydanticValidatorPipeline",
        "structured_output/retry_on_parse_failure.py::RetryOnParseFailure",
        "structured_output/yaml_extractor_pipeline.py::YamlExtractorPipeline",
    }
)

#: `with Tapestry():` opened and never run. Its only effect is to stop the knots
#: built inside it leaking into the outer graph — so those knots are constructed,
#: never executed, and invisible.
UNRUN_TAPESTRY = frozenset(
    {
        "lats/lats_search.py::LatsSearch",
        "plan_react/plan_react_pipeline.py::PlanReActPipeline",
        "reflexion/reflexion_pipeline.py::ReflexionPipeline",
    }
)


def _pipeline_process_methods() -> list[tuple[str, ast.AST]]:
    """Return ``(label, process_ast)`` for every SubTapestry under specializations/.

    Membership is decided at runtime (``issubclass``) so a renamed base cannot
    silently drop a class out of scope; the body is read from the AST because
    that is the only place the bypass is visible.
    """
    root = Path(_specializations_pkg.__path__[0])
    found: dict[str, ast.AST] = {}

    for info in pkgutil.walk_packages(
        _specializations_pkg.__path__, _specializations_pkg.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue
        owned = {
            obj.__qualname__
            for name in dir(module)
            if isinstance(obj := getattr(module, name), type)
            and issubclass(obj, SubTapestry)
            and obj.__module__ == info.name
        }
        if not owned:
            continue
        rel = Path(module_file).relative_to(root)
        tree = ast.parse(Path(module_file).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in owned:
                continue
            process = next(
                (
                    child
                    for child in node.body
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                    and child.name == "process"
                ),
                None,
            )
            if process is not None:
                found[f"{rel}::{node.name}"] = process
    return sorted(found.items())


def _awaits_child_process(process: ast.AST) -> bool:
    """True if the body awaits some *other* object's ``process()``."""
    for node in ast.walk(process):
        if not (isinstance(node, ast.Await) and isinstance(node.value, ast.Call)):
            continue
        func = node.value.func
        if not (isinstance(func, ast.Attribute) and func.attr == "process"):
            continue
        receiver = func.value
        is_self = isinstance(receiver, ast.Name) and receiver.id == "self"
        is_super = isinstance(receiver, ast.Call) and getattr(receiver.func, "id", "") == "super"
        if not (is_self or is_super):
            return True
    return False


def _returns_inline_source(process: ast.AST) -> bool:
    """True if the returned sink is a ``Source`` subclass defined in the body.

    Only the *returned* one counts. A locally-defined `Source` that seeds a real
    graph is legitimate, and flagging it would make this guard something authors
    route around rather than obey.
    """
    inline = {
        node.name
        for node in ast.walk(process)
        if isinstance(node, ast.ClassDef)
        and {base.id for base in node.bases if isinstance(base, ast.Name)} & {"Source"}
    }
    if not inline:
        return False
    return any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) in inline
        for node in ast.walk(process)
    )


def _opens_unrun_tapestry(process: ast.AST) -> bool:
    """True if a ``with Tapestry()`` is opened and never passed to ``_run_inner``."""
    opened: set[str] = set()
    executed: set[str] = set()
    for node in ast.walk(process):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call) and getattr(expr.func, "id", "") == "Tapestry":
                    target = item.optional_vars
                    opened.add(target.id if isinstance(target, ast.Name) else "<unbound>")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_run_inner"
        ):
            executed.update(arg.id for arg in node.args if isinstance(arg, ast.Name))
    return bool(opened - executed)


class TestNoNewEngineBypass(unittest.TestCase):
    """Freeze the bypass inventory. Exact equality in both directions."""

    def setUp(self) -> None:
        self.pipelines = _pipeline_process_methods()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason."""
        assert len(self.pipelines) >= 40, len(self.pipelines)

    def test_awaiting_a_child_process_is_frozen(self) -> None:
        found = {label for label, proc in self.pipelines if _awaits_child_process(proc)}
        assert found == AWAITS_CHILD_PROCESS, {
            "new bypasses": sorted(found - AWAITS_CHILD_PROCESS),
            "fixed — remove from AWAITS_CHILD_PROCESS": sorted(AWAITS_CHILD_PROCESS - found),
        }

    def test_returning_an_inline_source_is_frozen(self) -> None:
        found = {label for label, proc in self.pipelines if _returns_inline_source(proc)}
        assert found == RETURNS_INLINE_SOURCE, {
            "new bypasses": sorted(found - RETURNS_INLINE_SOURCE),
            "fixed — remove from RETURNS_INLINE_SOURCE": sorted(RETURNS_INLINE_SOURCE - found),
        }

    def test_unrun_tapestries_are_frozen(self) -> None:
        found = {label for label, proc in self.pipelines if _opens_unrun_tapestry(proc)}
        assert found == UNRUN_TAPESTRY, {
            "new bypasses": sorted(found - UNRUN_TAPESTRY),
            "fixed — remove from UNRUN_TAPESTRY": sorted(UNRUN_TAPESTRY - found),
        }


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code.

    Without these, an allowlist that matches a detector which silently stopped
    working would still be green — the failure mode a ratchet is most prone to.
    """

    @staticmethod
    def _process_of(source: str) -> ast.AST:
        tree = ast.parse(source)
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        return next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "process"
        )

    CLEAN = """
class P:
    async def process(self, x, **_):
        a = Alpha(value=x, _config=KnotConfig(id="a"))
        return Beta(source=a, _config=KnotConfig(id="b"))
"""

    def test_clean_pipeline_trips_nothing(self) -> None:
        proc = self._process_of(self.CLEAN)
        assert not _awaits_child_process(proc)
        assert not _returns_inline_source(proc)
        assert not _opens_unrun_tapestry(proc)

    def test_awaiting_self_process_is_allowed(self) -> None:
        """Recursion into one's own `process` is not a bypass."""
        proc = self._process_of(
            "class P:\n    async def process(self, **_):\n        return await self.process()\n"
        )
        assert not _awaits_child_process(proc)

    def test_awaiting_a_child_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, child, **_):\n"
            "        return await child.process(x=1)\n"
        )
        assert _awaits_child_process(proc)

    def test_returned_inline_source_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        v = compute()\n"
            "        class _R(Source):\n"
            "            async def process(self, **_):\n"
            "                return v\n"
            "        return _R(_config=KnotConfig(id='r'))\n"
        )
        assert _returns_inline_source(proc)

    def test_inline_source_that_seeds_a_graph_is_allowed(self) -> None:
        """It is the *returned* sink that matters, not the class's existence."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        class _Seed(Source):\n"
            "            async def process(self, **_):\n"
            "                return 0\n"
            "        seed = _Seed(_config=KnotConfig(id='s'))\n"
            "        return Real(state=seed, _config=KnotConfig(id='r'))\n"
        )
        assert not _returns_inline_source(proc)

    def test_unrun_tapestry_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        with Tapestry():\n"
            "            Alpha(_config=KnotConfig(id='a'))\n"
            "        return Beta(_config=KnotConfig(id='b'))\n"
        )
        assert _opens_unrun_tapestry(proc)

    def test_a_tapestry_passed_to_run_inner_is_allowed(self) -> None:
        """The sanctioned shape: resolve a value, then build the rest from it."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        with Tapestry() as inner:\n"
            "            Alpha(_config=KnotConfig(id='a'))\n"
            "        result = await self._run_inner(inner)\n"
            "        return Beta(v=result.outputs['a'], _config=KnotConfig(id='b'))\n"
        )
        assert not _opens_unrun_tapestry(proc)
