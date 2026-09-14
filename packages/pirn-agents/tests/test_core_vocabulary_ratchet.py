"""Freeze the "agents speaks core" vocabulary-drift inventory (ADR WS2).

The ADR (``.prompticorn/sessions/agents-realignment-proposal-20260913.md``)
retires three agents-local parallels to a core primitive:

(a) an agents exception hierarchy that does not root on
    :class:`pirn.exceptions.pirn_error.PirnError`;
(b) ``CanonicalJson`` (deleted, PIR-872) as a parallel canonicaliser to
    :meth:`pirn.core.content_hasher.ContentHasher.hash`;
(c) an outcome enum modelling success/failure/skip beside core's
    ``Ok | Err | Skipped`` ``Result``.

PIR-872 burned all three inventories down to empty; each is kept as an empty
exact-equality assertion so a reintroduction fails loudly.

Like ``tests/specializations/base/test_no_engine_bypass.py``, this is a
ratchet, not a clean assertion: WS2 burns down (a) for the files it owns
(``exceptions/**``, ``security/**``) and leaves the rest — other lanes own
``llm/``, ``mcp/``, ``prompt/``, ``performance/``, ``resilience/``,
``memory/``, ``specializations/`` — as an inventory for their own workstreams
(see the WS2 report). (b) and (c) are call-site inventories only: WS2's
report explains, per class, why the underlying migration is deferred rather
than executed in this pass.

The allowlists are asserted by **exact equality**, deliberately:

* a new instance of the pattern fails, because the finding is not listed;
* fixing one *without* updating the list also fails, because the list still
  names it — which is what keeps the list from rotting into a lie.

Regenerate by running the discovery methods below directly (see
``VocabularyInventory`` in ``tests/vocabulary_inventory.py``) and diffing
against the constants here.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.vocabulary_inventory import VocabularyInventory

_PACKAGE_ROOT = Path(__file__).parent.parent / "pirn_agents"

# --- (a) exception roots without PirnError, frozen -------------------------
#
# A "root" is an exception class whose own immediate bases are all builtins
# (or another agents exception that is itself unfixed) — i.e. every class
# below is the class that would need `PirnError` added to its own bases; a
# subclass of an already-fixed root (`ToolNotFoundError(ToolInvocationError)`,
# ...) is not listed here because it
# inherits `PirnError` transitively the moment its root is fixed, and this
# ratchet checks the resolved MRO, not immediate bases.
#
# WS2 fixed the 8 roots under exceptions/** and security/** (its lane):
# ToolInvocationError, AgentRecursionError (since deleted, PIR-872), SandboxDisabledError,
# UnsupportedModalityError, MissingCassetteEntryError (since deleted, PIR-872), InjectionDetectedError,
# McpTrustError, UntrustedDirectiveError. PIR-872 rooted the remaining nine on
# PirnError (keeping each one's builtin base where callers catch it):
# BudgetBreachError, StructuredDecodeError, SpecialistInvocationError,
# ConstitutionalViolationError, McpError, PromptRenderError, CircuitOpenError,
# LLMProviderError, RateLimitSignal -- and deleted KeyIndexUnreadableError,
# whose only raiser (MemoryStoreKeyIndex) PIR-864 had already deleted. Empty,
# not deleted: a new agents exception root without PirnError fails here.
EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR: frozenset[str] = frozenset()

# --- (b) modules importing CanonicalJson ------------------------------------
#
# `CanonicalJson`/`OpaquePolicy` are deleted (PIR-872): every former caller
# (`determinism/content_digest.py`, `evaluation/trajectory_call_key.py`, and
# earlier `builder/agent_knot_id_factory.py`,
# `resilience/idempotency_key_assigner.py`) calls
# `pirn.core.content_hasher.ContentHasher.hash(..., strict=True)` directly. Kept as an empty
# assertion so a reintroduced parallel canonicaliser is loud.
CANONICAL_JSON_IMPORTERS: frozenset[str] = frozenset()

# --- (c) outcome enums beside Result ----------------------------------------
#
# An outcome is `Ok | Err | Skipped`. PIR-872 deleted the last four parallel
# enums: `BatchItemStatus` (`BatchItemResult.outcome` is the item's `Result`; a
# timeout is an `Err` whose error type is `KnotTimeoutError`), `ToolStatus`
# (`ToolResult.outcome` is the call's `Result`; the model-facing `status` is a
# string derived from it), `FailoverOutcome` (`FailoverAttempt.result` already
# carried the `Result`; a circuit-open skip is `Skipped(reason="circuit_open")`),
# and `RetryClassification` -- not an outcome at all but a two-valued
# retry-safety verdict about an error, now `RetrySafetyClassifier.is_safe()`
# returning a `bool`. Empty, not deleted: the self-test below still fails on any
# new enum with both an OK-like and an ERROR-like member.
OUTCOME_ENUMS_BESIDE_RESULT: frozenset[str] = frozenset()


class TestExceptionRootsFrozen(unittest.TestCase):
    """(a) every agents exception root either has PirnError, or is listed here."""

    def setUp(self) -> None:
        self.classes = VocabularyInventory.discover_classes(_PACKAGE_ROOT)

    def test_the_walk_is_not_vacuous(self) -> None:
        exception_classes = [
            name
            for name in self.classes
            if VocabularyInventory.is_exception_class(name, self.classes)
        ]
        assert len(exception_classes) >= 10, exception_classes

    def test_roots_without_pirn_error_are_frozen(self) -> None:
        roots_without_pirn_error = {
            f"{path}::{name}"
            for name, (path, bases) in self.classes.items()
            if VocabularyInventory.is_exception_class(name, self.classes)
            and not VocabularyInventory.roots_on_pirn_error(name, self.classes)
            # a "root" here: none of its own immediate bases are themselves
            # an unfixed exception class in this same set (else it is a
            # subclass already covered by its root's line).
            and not any(
                base in self.classes
                and VocabularyInventory.is_exception_class(base, self.classes)
                and not VocabularyInventory.roots_on_pirn_error(base, self.classes)
                for base in bases
            )
        }
        assert roots_without_pirn_error == EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR, {
            "new roots missing PirnError": sorted(
                roots_without_pirn_error - EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR
            ),
            "fixed -- remove from EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR": sorted(
                EXCEPTION_ROOTS_WITHOUT_PIRN_ERROR - roots_without_pirn_error
            ),
        }

    def test_pir872_roots_now_have_pirn_error(self) -> None:
        """The 9 roots PIR-872 fixed must actually resolve PirnError."""
        for name in (
            "BudgetBreachError",
            "StructuredDecodeError",
            "SpecialistInvocationError",
            "ConstitutionalViolationError",
            "McpError",
            "PromptRenderError",
            "CircuitOpenError",
            "LLMProviderError",
            "RateLimitSignal",
        ):
            assert name in self.classes, f"{name} not found by the walk"
            assert VocabularyInventory.roots_on_pirn_error(name, self.classes), name

    def test_ws2_owned_roots_now_have_pirn_error(self) -> None:
        """The roots WS2 fixed must actually resolve PirnError, not just be absent above.

        WS2 fixed 8; ``AgentRecursionError`` (core ``RunNesting``) and
        ``MissingCassetteEntryError`` (core replay) were since deleted (PIR-872).
        """
        fixed = [
            "ToolInvocationError",
            "SandboxDisabledError",
            "UnsupportedModalityError",
            "InjectionDetectedError",
            "McpTrustError",
            "UntrustedDirectiveError",
        ]
        for name in fixed:
            assert name in self.classes, f"{name} not found by the walk"
            assert VocabularyInventory.roots_on_pirn_error(name, self.classes), name

    def test_subclasses_of_fixed_roots_inherit_pirn_error(self) -> None:
        for name in (
            "ToolCancelledError",
            "ToolNotFoundError",
            "ToolArgumentValidationError",
        ):
            assert VocabularyInventory.roots_on_pirn_error(name, self.classes), name


class TestCanonicalJsonImportersFrozen(unittest.TestCase):
    """(b) every module importing CanonicalJson is listed here."""

    def test_importers_are_frozen(self) -> None:
        found = {
            path.relative_to(_PACKAGE_ROOT).as_posix()
            for path in VocabularyInventory.iter_py_files(_PACKAGE_ROOT)
            if VocabularyInventory.imports_canonical_json(path)
        }
        assert found == CANONICAL_JSON_IMPORTERS, {
            "new importers": sorted(found - CANONICAL_JSON_IMPORTERS),
            "migrated off CanonicalJson -- remove from CANONICAL_JSON_IMPORTERS": sorted(
                CANONICAL_JSON_IMPORTERS - found
            ),
        }

    def test_detector_recognises_a_from_import_shape(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "user.py"
            module.write_text(
                "from pirn_agents.serialization.canonical_json import CanonicalJson\n"
            )
            assert VocabularyInventory.imports_canonical_json(module)

    def test_detector_ignores_an_unrelated_import(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "user.py"
            module.write_text("from pirn.core.content_hasher import ContentHasher\n")
            assert not VocabularyInventory.imports_canonical_json(module)


class TestOutcomeEnumsFrozen(unittest.TestCase):
    """(c) outcome enums beside Result are listed here (none remain), and are real Enums."""

    def setUp(self) -> None:
        self.classes = VocabularyInventory.discover_classes(_PACKAGE_ROOT)

    def test_the_enum_walk_is_not_vacuous(self) -> None:
        enums = [
            name for name in self.classes if VocabularyInventory.is_enum_class(name, self.classes)
        ]
        assert len(enums) >= 10, enums

    def test_every_listed_outcome_enum_resolves_to_a_real_enum(self) -> None:
        for label in OUTCOME_ENUMS_BESIDE_RESULT:
            path, _, name = label.partition("::")
            assert name in self.classes, f"{label}: class not found by the walk"
            found_path, _bases = self.classes[name]
            assert found_path == path, f"{label}: found at {found_path!r} instead"
            assert VocabularyInventory.is_enum_class(name, self.classes), (
                f"{label}: no longer an Enum subclass"
            )

    def test_no_other_ok_error_shaped_enum_is_missing_from_the_list(self) -> None:
        # Mechanical half of the otherwise-hand-curated list: any Enum whose
        # member names textually look like a Result-shaped outcome (has both
        # an OK/SUCCESS-ish member and an ERROR/FAIL-ish member) must already
        # be on the list, so a *new* one of this exact shape cannot slip in
        # unnoticed even though the list itself is curated by hand.
        ok_like = {"OK", "SUCCESS", "SUCCEEDED"}
        error_like = {"ERROR", "FAILED", "FAIL", "FAILURE"}
        listed_names = {label.rpartition("::")[2] for label in OUTCOME_ENUMS_BESIDE_RESULT}
        missed: list[str] = []
        for name, (path, _bases) in self.classes.items():
            if not VocabularyInventory.is_enum_class(name, self.classes):
                continue
            members = _enum_member_names(_PACKAGE_ROOT / path, name)
            if members & ok_like and members & error_like and name not in listed_names:
                missed.append(f"{path}::{name}")
        assert missed == [], missed


def _enum_member_names(path: Path, class_name: str) -> set[str]:
    """Return the upper-case assignment targets in ``class_name``'s body."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            names: set[str] = set()
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    names.update(t.id for t in stmt.targets if isinstance(t, ast.Name))
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    names.add(stmt.target.id)
            return names
    return set()


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code."""

    def setUp(self) -> None:
        self.classes: dict[str, tuple[str, list[str]]] = {
            "Clean": ("clean.py", []),
            "BuiltinRootedError": ("a.py", ["RuntimeError"]),
            "PirnRootedError": ("b.py", ["PirnError", "RuntimeError"]),
            "ChildOfPirnRooted": ("c.py", ["PirnRootedError"]),
            "ChildOfBuiltinRooted": ("d.py", ["BuiltinRootedError"]),
            "PlainEnum": ("e.py", ["Enum"]),
            "StrEnum": ("f.py", ["str", "Enum"]),
            "SubclassOfEnum": ("g.py", ["PlainEnum"]),
            "NotAnEnum": ("h.py", ["object"]),
        }

    def test_clean_class_is_not_an_exception(self) -> None:
        assert not VocabularyInventory.is_exception_class("Clean", self.classes)

    def test_builtin_rooted_is_an_exception_without_pirn_error(self) -> None:
        assert VocabularyInventory.is_exception_class("BuiltinRootedError", self.classes)
        assert not VocabularyInventory.roots_on_pirn_error("BuiltinRootedError", self.classes)

    def test_pirn_rooted_has_pirn_error(self) -> None:
        assert VocabularyInventory.is_exception_class("PirnRootedError", self.classes)
        assert VocabularyInventory.roots_on_pirn_error("PirnRootedError", self.classes)

    def test_child_of_pirn_rooted_inherits_pirn_error_transitively(self) -> None:
        assert VocabularyInventory.roots_on_pirn_error("ChildOfPirnRooted", self.classes)

    def test_child_of_builtin_rooted_does_not_have_pirn_error(self) -> None:
        assert VocabularyInventory.is_exception_class("ChildOfBuiltinRooted", self.classes)
        assert not VocabularyInventory.roots_on_pirn_error("ChildOfBuiltinRooted", self.classes)

    def test_plain_and_str_enum_are_recognised(self) -> None:
        assert VocabularyInventory.is_enum_class("PlainEnum", self.classes)
        assert VocabularyInventory.is_enum_class("StrEnum", self.classes)

    def test_subclass_of_an_enum_is_recognised_transitively(self) -> None:
        assert VocabularyInventory.is_enum_class("SubclassOfEnum", self.classes)

    def test_non_enum_is_not_recognised(self) -> None:
        assert not VocabularyInventory.is_enum_class("NotAnEnum", self.classes)

    def test_unresolvable_name_is_not_an_exception_or_enum(self) -> None:
        assert not VocabularyInventory.is_exception_class("Nowhere", self.classes)
        assert not VocabularyInventory.is_enum_class("Nowhere", self.classes)


if __name__ == "__main__":
    unittest.main()
