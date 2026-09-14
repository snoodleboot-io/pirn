"""``OneSchedulerInventory`` — find classes that schedule work themselves.

ADR agents-speaks-core, WS4b ("one scheduler"): batch/performance/resilience
code should dispatch through the core engine's ``Admission`` +
``GovernedDispatch`` and resume through ``RunHistory`` lineage, not through a
private ``asyncio.wait``/``asyncio.gather`` loop, a hand-held
``asyncio.Semaphore`` counting its own concurrency, or a checkpoint store
outside ``RunHistory``.

A source-only AST pass over each class's own body (not what it imports or
calls into), so this runs before the tree necessarily imports cleanly — the
same trade-off ``tests/core_seams/core_seam_shadow_inventory.py`` and
``tests/specializations/base/bypass_inventory.py`` make. Every detector
matches ``ast.Name``/``ast.Attribute`` identifiers, never raw source text, so
a docstring merely *mentioning* ``asyncio.Semaphore`` or ``SessionStore`` as
an example (a string constant, not an identifier node) cannot trip a
detector meant for a class that actually depends on the thing.

Detection deliberately does not follow delegation: ``Bulkhead`` constructing
a ``BackpressureSemaphore()`` *is* caught (its own body names a
"...Semaphore" callable, even though the semaphore itself lives one class
away), but a class that merely takes a ``Bulkhead`` as a parameter is not —
only the class whose own body constructs the concurrency primitive, or names
the checkpoint-store type, is a shadow.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

import pirn_agents

#: Directories this ratchet walks — the three WS4b owns
#: (``pirn_agents/{batch,performance,resilience}/``).
_OWNED_DIRS = ("batch", "performance", "resilience")

#: Names that mark a class as persisting through the pre-migration F14
#: session-store stack instead of ``RunHistory`` lineage.
_SESSION_STORE_NAMES = frozenset({"SessionStore", "RunCheckpoint", "RunState", "BatchCheckpointer"})


class OneSchedulerInventory:
    """Discovers ``pirn_agents`` classes that schedule or checkpoint outside the engine."""

    _ASYNCIO_LOOP_ATTRS: ClassVar[frozenset[str]] = frozenset({"wait", "gather", "ensure_future"})
    _BARE_LOOP_NAMES: ClassVar[frozenset[str]] = frozenset({"gather", "ensure_future"})

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return ``{detector: {"relative/path.py::ClassName", ...}}`` over the owned dirs."""
        root = Path(pirn_agents.__path__[0])
        found: dict[str, set[str]] = {
            "asyncio_loop": set(),
            "own_concurrency_limit": set(),
            "checkpoints_outside_run_history": set(),
        }
        for owned in _OWNED_DIRS:
            for path in sorted((root / owned).rglob("*.py")):
                if any(part in {"tests", "__pycache__"} for part in path.parts):
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                relative = path.relative_to(root).as_posix()
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    label = f"{relative}::{node.name}"
                    if cls.schedules_own_asyncio_loop(node):
                        found["asyncio_loop"].add(label)
                    if cls.holds_own_concurrency_limit(node):
                        found["own_concurrency_limit"].add(label)
                    if cls.checkpoints_outside_run_history(node):
                        found["checkpoints_outside_run_history"].add(label)
        return {name: frozenset(labels) for name, labels in found.items()}

    @classmethod
    def schedules_own_asyncio_loop(cls, node: ast.ClassDef) -> bool:
        """Whether *node*'s own body calls ``asyncio.wait``/``gather``/``ensure_future``.

        Matches ``asyncio.wait(...)`` / ``asyncio.gather(...)`` /
        ``asyncio.ensure_future(...)`` (module-qualified, so an unrelated
        ``self._event.wait()`` — an ``asyncio.Event``'s own method, a
        different thing entirely — does not trip it), plus a bare
        ``gather(...)``/``ensure_future(...)`` reached via
        ``from asyncio import gather``. Bare ``wait(...)`` is deliberately
        excluded from the bare-name form: unlike ``gather``/``ensure_future``,
        ``.wait()`` is a common method name on ``asyncio.Event``,
        ``asyncio.Condition``, and this package's own
        :class:`~pirn_agents.performance.cancellation_token.CancellationToken`,
        so a bare-name match would fire on those constantly.
        """
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "asyncio" and func.attr in cls._ASYNCIO_LOOP_ATTRS:
                    return True
            elif isinstance(func, ast.Name) and func.id in cls._BARE_LOOP_NAMES:
                return True
        return False

    @staticmethod
    def holds_own_concurrency_limit(node: ast.ClassDef) -> bool:
        """Whether *node*'s own body constructs an ``asyncio.Semaphore``-shaped pool.

        Matches a call whose final identifier is or ends with ``Semaphore``
        (``asyncio.Semaphore(...)``, a bare ``Semaphore(...)``, or
        ``BackpressureSemaphore(...)``) — a private in-flight budget the
        engine's ``Admission``/``ConcurrencyLimits`` cannot see or steer.
        Only ``ast.Name``/``ast.Attribute`` identifiers are matched, so a
        docstring's prose example never trips this.
        """
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            name = func.id if isinstance(func, ast.Name) else None
            if name is None and isinstance(func, ast.Attribute):
                name = func.attr
            if name is not None and name.endswith("Semaphore"):
                return True
        return False

    @staticmethod
    def checkpoints_outside_run_history(node: ast.ClassDef) -> bool:
        """Whether *node*'s own body names the pre-migration F14 session-store stack.

        ``RunHistory``/``KnotLineage`` is the one durable ledger a resumable
        batch should read; a class whose body actually references
        ``SessionStore`` / ``RunCheckpoint`` / ``RunState`` /
        ``BatchCheckpointer`` — as a type annotation, an import, or a
        constructor call — persists (or reads) progress through the store a
        real agent run checkpoints to, exactly the parallel store this
        workstream retired ``MapAgent`` off of, kept importable only as a
        deprecated shim. Matches identifier nodes only, so a docstring
        merely discussing the pre-migration design in prose never trips this.
        """
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in _SESSION_STORE_NAMES:
                return True
            if isinstance(sub, ast.Attribute) and sub.attr in _SESSION_STORE_NAMES:
                return True
        return False
