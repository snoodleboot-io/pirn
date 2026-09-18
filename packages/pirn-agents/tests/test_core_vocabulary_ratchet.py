"""Guard: agents speaks core's vocabulary, not a parallel one (ADR WS2).

The ADR (``.prompticorn/sessions/agents-realignment-proposal-20260913.md``)
retires three agents-local parallels to a core primitive:

(a) an agents exception hierarchy that does not root on
    :class:`pirn.exceptions.pirn_error.PirnError`;
(b) a canonicaliser-and-digest of its own beside
    :meth:`pirn.core.content_hasher.ContentHasher.hash`, which owns content
    identity — one canonical form, one digest, one thing a run can correlate;
(c) an outcome enum modelling success/failure/skip beside core's
    ``Ok | Err | Skipped`` ``Result``.

Each rule is asserted directly. All three were previously frozen as empty
exact-equality sets of names, and (b) went further wrong: it asked which modules
imported the name ``CanonicalJson``, which stopped meaning anything the moment
that class was deleted — a module can canonicalise and hash content without ever
mentioning it. (b) now detects the *shape*, the content-hashing import
(:meth:`~tests.source_shapes.SourceShapes.imports_hashing`), and each rule's
detector is pinned by a test that feeds it a violating snippet.
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes
from tests.vocabulary_inventory import VocabularyInventory

# There are no allowlists in this module. Each of the three rules below was
# frozen as an (empty) exact-equality set of names; all three are now asserted
# directly, so a new instance fails against the rule rather than against a list
# someone has to remember to keep honest.
#
# (b) also changed detector. It asked which modules imported the name
# `CanonicalJson` — a question that stopped meaning anything the moment that
# class was deleted, because a module can canonicalise and hash content without
# ever mentioning it. The shape it stood for is *content hashing*, which core's
# `ContentHasher` owns (one canonical form, one digest, one thing the run can
# correlate), so that is what is detected now: any module reaching for a hashing
# library of its own.


class TestExceptionRootsFrozen(unittest.TestCase):
    """(a) every agents exception root resolves ``PirnError``."""

    def setUp(self) -> None:
        self.classes = VocabularyInventory.discover_classes(AgentsSourceIndex.package_root())

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
        assert roots_without_pirn_error == set(), sorted(roots_without_pirn_error)

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


class TestContentIdentityIsCores(unittest.TestCase):
    """(b) no module hashes content for itself; ``ContentHasher`` owns identity."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.modules()) >= 500, len(AgentsSourceIndex.modules())

    def test_no_module_reaches_for_a_hashing_library(self) -> None:
        found = {
            relative: sorted(SourceShapes.imports_hashing(tree))
            for relative, tree in AgentsSourceIndex.modules().items()
            if SourceShapes.imports_hashing(tree)
        }
        assert found == {}, found

    def test_rule_fires_on_a_module_importing_hashlib(self) -> None:
        assert SourceShapes.imports_hashing(
            ast.parse("import hashlib\n\n\nclass Digest:\n    pass\n")
        ) == frozenset({"hashlib"})

    def test_rule_fires_on_a_from_import_of_a_hashing_library(self) -> None:
        """A shape the ``CanonicalJson`` name match could not see."""
        assert SourceShapes.imports_hashing(ast.parse("from hashlib import blake2b\n")) == (
            frozenset({"hashlib"})
        )

    def test_rule_fires_on_a_third_party_hasher(self) -> None:
        assert SourceShapes.imports_hashing(ast.parse("import xxhash\n")) == frozenset({"xxhash"})

    def test_rule_ignores_asking_core_for_the_digest(self) -> None:
        assert (
            SourceShapes.imports_hashing(
                ast.parse("from pirn.core.content_hasher import ContentHasher\n")
            )
            == frozenset()
        )

    def test_rule_ignores_an_unrelated_import(self) -> None:
        assert SourceShapes.imports_hashing(ast.parse("import json\n")) == frozenset()


class TestOutcomeEnumsFrozen(unittest.TestCase):
    """(c) no Enum models success-and-failure beside core's ``Ok | Err | Skipped``."""

    def setUp(self) -> None:
        self.classes = VocabularyInventory.discover_classes(AgentsSourceIndex.package_root())

    def test_the_enum_walk_is_not_vacuous(self) -> None:
        enums = [
            name for name in self.classes if VocabularyInventory.is_enum_class(name, self.classes)
        ]
        assert len(enums) >= 10, enums

    @staticmethod
    def _member_names(path: Path, class_name: str) -> set[str]:
        """Return the assignment targets in ``class_name``'s body."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                names: set[str] = set()
                for statement in node.body:
                    if isinstance(statement, ast.Assign):
                        names.update(
                            target.id
                            for target in statement.targets
                            if isinstance(target, ast.Name)
                        )
                    elif isinstance(statement, ast.AnnAssign) and isinstance(
                        statement.target, ast.Name
                    ):
                        names.add(statement.target.id)
                return names
        return set()

    @classmethod
    def _outcome_shaped(cls, path: Path, class_name: str) -> bool:
        """Whether the Enum carries both an OK-like and an ERROR-like member."""
        members = cls._member_names(path, class_name)
        return bool(members & {"OK", "SUCCESS", "SUCCEEDED"}) and bool(
            members & {"ERROR", "FAILED", "FAIL", "FAILURE"}
        )

    def test_no_enum_models_an_outcome(self) -> None:
        """An Enum carrying both an OK-like and an ERROR-like member is a ``Result``."""
        found = [
            f"{path}::{name}"
            for name, (path, _bases) in self.classes.items()
            if VocabularyInventory.is_enum_class(name, self.classes)
            and self._outcome_shaped(AgentsSourceIndex.package_root() / path, name)
        ]
        assert found == [], sorted(found)

    def test_rule_fires_on_an_outcome_shaped_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "batch_item_status.py"
            module.write_text(
                'class BatchItemStatus(str, Enum):\n    OK = "ok"\n    FAILED = "failed"\n'
            )
            assert self._outcome_shaped(module, "BatchItemStatus")

    def test_rule_ignores_an_enum_that_is_not_an_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "finish_reason.py"
            module.write_text(
                'class FinishReason(str, Enum):\n    STOP = "stop"\n    LENGTH = "length"\n'
            )
            assert not self._outcome_shaped(module, "FinishReason")


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
