"""PIR-790: the import paths the trigger/streaming docs hand to users must work.

``pirn/triggers/__init__.py`` and ``pirn/streaming/__init__.py`` intentionally
export nothing — PIR-744 stripped the package façades because the house
convention forbids import forwarding, and
``scripts/check_no_import_forwarding.py`` enforces that workspace-wide.

The docs, however, still told users to write ``from pirn.triggers import
run_forever``, which raises ``ImportError``.

These tests read the doc files themselves.  Every ``from pirn.triggers…`` and
``from pirn.streaming…`` line inside a fenced code block is extracted and
actually resolved, so a doc edit that reintroduces a façade import — or names
a symbol that has moved — fails here rather than in a user's terminal.  The
companion tests below pin the deliberate absence of the re-exports, so the
two halves cannot drift apart.

Prose is not scanned, only fenced code blocks: ``triggers/AGENTIC_USE.md``
deliberately quotes ``from pirn.triggers import run_forever`` inline as the
counter-example, and that must stay quotable.
"""

from __future__ import annotations

import importlib
import re
import unittest
from pathlib import Path

import pirn.streaming
import pirn.triggers

#: Doc files shipped inside the package — always present, wherever the tests run.
_PACKAGE_DOCS = (
    Path(pirn.triggers.__file__).parent / "AGENTIC_USE.md",
    Path(pirn.streaming.__file__).parent / "AGENTIC_USE.md",
)

#: Repo root, present only in a monorepo checkout (not in an installed sdist).
_REPO_ROOT = Path(__file__).resolve().parents[5]

#: Repo-level docs that publish trigger/streaming imports, including the
#: mkdocs site pages served to the public.
_REPO_DOCS = (
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "api" / "triggers.md",
    _REPO_ROOT / "docs" / "api" / "streaming.md",
    _REPO_ROOT / "docs" / "cookbook" / "streaming.md",
    _REPO_ROOT / "docs" / "guides" / "deployment.md",
)

_IN_MONOREPO = (_REPO_ROOT / "mkdocs.yml").is_file()

_FENCE = re.compile(r"^\s*```")
_IMPORT = re.compile(r"^\s*from\s+(pirn\.(?:triggers|streaming)[\w.]*)\s+import\s+(.+?)\s*$")


def _fenced_imports(path: Path) -> list[tuple[int, str, tuple[str, ...]]]:
    """Extract trigger/streaming import statements from fenced code blocks.

    Args:
        path: Markdown file to scan.

    Returns:
        One ``(line_number, module, symbols)`` triple per matching import.
    """
    found: list[tuple[int, str, tuple[str, ...]]] = []
    in_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        match = _IMPORT.match(line)
        if match is None:
            continue
        symbols = tuple(
            name.strip().split(" as ")[0].strip()
            for name in match.group(2).split(",")
            if name.strip()
        )
        found.append((lineno, match.group(1), symbols))
    return found


def _docs_under_test() -> tuple[Path, ...]:
    """Return the doc files to scan, adding the repo-level ones in a checkout.

    Returns:
        Existing markdown paths whose fenced code blocks are validated.
    """
    docs = list(_PACKAGE_DOCS)
    if _IN_MONOREPO:
        docs.extend(_REPO_DOCS)
    return tuple(d for d in docs if d.is_file())


class TestDocumentedImportsAreReal(unittest.TestCase):
    """Every trigger/streaming import printed in the docs is executed here."""

    def test_doc_set_is_present(self) -> None:
        # Without this the scan below would pass vacuously if the docs moved.
        for path in _PACKAGE_DOCS:
            with self.subTest(doc=path.name):
                self.assertTrue(path.is_file(), f"missing packaged doc: {path}")
        if _IN_MONOREPO:
            for path in _REPO_DOCS:
                with self.subTest(doc=str(path)):
                    self.assertTrue(path.is_file(), f"missing repo doc: {path}")

    def test_every_documented_import_resolves(self) -> None:
        checked = 0
        for path in _docs_under_test():
            for lineno, module_name, symbols in _fenced_imports(path):
                where = f"{path}:{lineno}"
                with self.subTest(doc=where, module=module_name):
                    try:
                        module = importlib.import_module(module_name)
                    except ImportError as exc:  # pragma: no cover - failure path
                        self.fail(f"{where}: `from {module_name} import …` fails: {exc}")
                    for symbol in symbols:
                        self.assertTrue(
                            hasattr(module, symbol),
                            f"{where}: {module_name} has no attribute {symbol!r}",
                        )
                        checked += 1
        # The docs really do publish these imports; a zero here means the
        # scanner stopped matching, not that the docs became clean.
        self.assertGreaterEqual(checked, 20, "doc scan found suspiciously few imports")

    def test_no_doc_imports_from_the_stripped_facades(self) -> None:
        offenders: list[str] = []
        for path in _docs_under_test():
            for lineno, module_name, _symbols in _fenced_imports(path):
                if module_name in ("pirn.triggers", "pirn.streaming"):
                    offenders.append(f"{path}:{lineno} -> from {module_name} import …")
        self.assertEqual(
            offenders,
            [],
            "docs import from a package façade that exports nothing; "
            "use the concrete module (pirn.triggers.cron, pirn.streaming.iterable, …)",
        )


class TestPackagesExposeNoFacade(unittest.TestCase):
    """The empty ``__init__`` façades stay empty — no import forwarding."""

    def test_trigger_package_forwards_nothing(self) -> None:
        package = importlib.import_module("pirn.triggers")
        for symbol in ("Trigger", "run_forever", "CronTrigger", "WebhookTrigger"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(package, symbol))

    def test_streaming_package_forwards_nothing(self) -> None:
        package = importlib.import_module("pirn.streaming")
        for symbol in ("StreamingSource", "run_stream", "IterableSource"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(package, symbol))


class TestConcreteModulePathsResolve(unittest.TestCase):
    """The concrete paths the docs are expected to hand out all exist."""

    def test_documented_trigger_paths_resolve(self) -> None:
        for module_name, symbol in (
            ("pirn.triggers.base", "Trigger"),
            ("pirn.triggers.base", "run_forever"),
            ("pirn.triggers.cron", "CronTrigger"),
            ("pirn.triggers.http", "WebhookTrigger"),
            ("pirn.triggers.kafka", "KafkaTrigger"),
            ("pirn.triggers.valkey", "ValKeyTrigger"),
        ):
            with self.subTest(module=module_name, symbol=symbol):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, symbol))

    def test_documented_streaming_paths_resolve(self) -> None:
        for module_name, symbol in (
            ("pirn.streaming.base", "StreamingSource"),
            ("pirn.streaming.base", "run_stream"),
            ("pirn.streaming.iterable", "IterableSource"),
            ("pirn.streaming.kafka", "KafkaStreamingSource"),
            ("pirn.streaming.file_tail", "FileTailSource"),
            ("pirn.streaming.trigger_adapter", "StreamingSourceTrigger"),
        ):
            with self.subTest(module=module_name, symbol=symbol):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, symbol))


class TestTapestryHasNoRunStream(unittest.TestCase):
    """``run_stream`` is a free function; the docs must not promise a method."""

    def test_tapestry_does_not_define_run_stream(self) -> None:
        tapestry_module = importlib.import_module("pirn.tapestry")
        self.assertFalse(hasattr(tapestry_module.Tapestry, "run_stream"))
