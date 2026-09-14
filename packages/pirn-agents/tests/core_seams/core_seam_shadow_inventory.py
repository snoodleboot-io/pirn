"""``CoreSeamShadowInventory`` — find every ``pirn_agents`` class that
re-implements a core seam the "agents speaks core" ADR (WS0) provides.

WS0 adds six seams to ``pirn-core``: ``KnotConfig.timeout`` / ``KnotConfig.retry``
(``KnotRetryPolicy``, ``KnotTimeoutError``), the nested-run depth and cycle guard
(``RunNesting``, ``NestingDepthExceededError``, ``NestedRunCycleError``), the
declared input schema for factory-built knots, the admission-gate runtime feedback
(``AdmissionGate.set_limit`` + ``AdmissionObserver``), the ``Check`` node role,
and the awaitable ``LoopSubTapestry.astep`` / ``afold``.  Each of them replaces a
parallel implementation that grew inside ``pirn_agents`` while core lacked the
seam.  Downstream workstreams (WS1-WS6) migrate those onto the core seams; this
inventory is what they burn down.

Shared by ``test_core_seam_shadows.py`` (the frozen ratchet asserted by exact
equality) and by nothing else yet — keeping the walk and the detector here means
the ratchet only compares "what the tree looks like now" against what it froze.

A class is a *shadow* of a seam when its name matches one of that seam's
patterns **and** it does not subclass the core seam class (a thin deprecation
shim over the core class keeps the public name but is no longer a parallel
implementation, so it drops out of the inventory).  Detection is a source-only
AST pass: bases are matched by their final name, since full import resolution is
out of scope for a gate that must run before the tree imports cleanly.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import ClassVar

import pirn_agents


class CoreSeamShadowInventory:
    """Discovers ``pirn_agents`` classes that shadow a WS0 core seam."""

    #: Seam name -> (class-name patterns that mark a shadow, core seam class
    #: names a subclass of which is a shim rather than a shadow).
    SEAMS: ClassVar[dict[str, tuple[tuple[str, ...], frozenset[str]]]] = {
        "retry_timeout": (
            (r"^RetryPolicy$", r"^ToolTimeoutError$"),
            frozenset({"KnotRetryPolicy", "KnotTimeoutError"}),
        ),
        "nesting": (
            (
                r"^AgentNestingConfig$",
                r"^AgentToolContext$",
                r"^AgentInvoker$",
                r"^AgentRecursionError$",
                r"^AgentDepthExceededError$",
                r"^AgentCycleError$",
            ),
            frozenset({"RunNesting", "NestingDepthExceededError", "NestedRunCycleError"}),
        ),
        "input_schema": (
            (r"^ToolSchemaCompiler$", r"^ArgumentValidator$", r"^AgentSchemaDeriver$"),
            frozenset({"KnotFactory", "Knot"}),
        ),
        "admission_feedback": (
            (
                r"^AdaptiveConcurrencyController$",
                r"^ConcurrencyConfig$",
                r"^BackpressureSemaphore$",
                r"^Bulkhead$",
                r"^BulkheadConfig$",
                r"^AsyncFanoutEngine$",
                r"^_FanoutRunner$",
                r"^BatchScheduler$",
            ),
            frozenset({"AdmissionObserver", "AdmissionGate", "ConcurrencyLimits"}),
        ),
        "check_role": (
            (r"^GatedAgentResponse$",),
            frozenset({"Check", "Gate"}),
        ),
        # A batch of independent calls needs no loop step at all: one knot per
        # call under an ``Aggregator`` inside a ``SubTapestry``, with core's
        # ``GovernedDispatch`` owning per-call retry backoff and timeout
        # (PIR-872). A hand-rolled ``asyncio.gather`` inside such a container
        # is still caught by ``USES_ASYNCIO_GATHER`` in test_no_engine_bypass.
        "async_loop_step": (
            (r"^ParallelToolExecutor$",),
            frozenset({"LoopSubTapestry", "AgentLoopPipeline", "SubTapestry"}),
        ),
    }

    @staticmethod
    def _base_name(base: ast.expr) -> str | None:
        """Return the final name of a base expression (``Gate`` for ``gate.Gate``)."""
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
        if isinstance(base, ast.Subscript):
            return CoreSeamShadowInventory._base_name(base.value)
        return None

    @classmethod
    def is_shadow(cls, node: ast.ClassDef, seam: str) -> bool:
        """Whether *node* is a shadow of *seam*: name matches, no core-seam base."""
        patterns, core_bases = cls.SEAMS[seam]
        if not any(re.match(pattern, node.name) for pattern in patterns):
            return False
        for base in node.bases:
            if cls._base_name(base) in core_bases:
                return False
        return True

    @staticmethod
    def top_level_classes() -> dict[str, ast.ClassDef]:
        """Return every top-level class in ``pirn_agents`` as ``{"path.py::Name": node}``."""
        root = Path(pirn_agents.__path__[0])
        classes: dict[str, ast.ClassDef] = {}
        for path in sorted(root.rglob("*.py")):
            if any(part in {"tests", "__pycache__"} for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative = path.relative_to(root).as_posix()
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    classes[f"{relative}::{node.name}"] = node
        return classes

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return ``{seam: {"relative/path.py::ClassName", ...}}`` over ``pirn_agents``."""
        found: dict[str, set[str]] = {seam: set() for seam in cls.SEAMS}
        for label, node in cls.top_level_classes().items():
            for seam in cls.SEAMS:
                if cls.is_shadow(node, seam):
                    found[seam].add(label)
        return {seam: frozenset(labels) for seam, labels in found.items()}
