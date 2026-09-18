"""Check the Python code and pirn import paths quoted in one markdown file."""

from __future__ import annotations

import ast
import re
from operator import attrgetter
from typing import ClassVar

from gatekit.doc_finding import DocFinding
from gatekit.fenced_code_block import FencedCodeBlock
from gatekit.inline_code_span import InlineCodeSpan
from gatekit.markdown_code_blocks import MarkdownCodeBlocks
from gatekit.source_import_resolver import SourceImportResolver


class DocImportAuditor:
    """Apply the three documentation rules to a markdown file's text.

    * ``doc_code_block_syntax`` — a python/py/pycon block must parse.
    * ``doc_unresolved_import`` — a pirn import in a block must resolve to source.
    * ``doc_unresolved_path`` — a dotted pirn path in an inline code span must resolve.

    An inline span that is itself an import statement (``from pirn.x import Y``) is
    held to ``doc_unresolved_import``; a span naming a file (``pirn_explorer.html``)
    is not a dotted path and is not checked. A span that is a quoted string literal
    (``"pirn.run_id"``) is prose about a *string value* — an OpenTelemetry attribute
    key, a filter expression, a YAML value — never a Python path, so it is not
    checked either; only a *bare* dotted token is held to ``doc_unresolved_path``.

    A class a document defines itself, in one of its own earlier fenced blocks, is
    "self-taught": a worked example that shows a reader how to build something is not
    lying about the repository's current contents, so importing that class later in
    the same document (e.g. from the test snippet that follows a "create this file"
    walkthrough) is not held to ``doc_unresolved_import`` either. A class the document
    only ever imports — never defines — gets no such pass.
    """

    _python_tags: ClassVar[frozenset[str]] = frozenset(
        {"python", "py", "python3", "pycon"}
    )
    _dotted: ClassVar[re.Pattern[str]] = re.compile(
        r"^(pirn|pirn_[a-z0-9_]+)(\.[A-Za-z_][A-Za-z0-9_]*)+$"
    )
    _inline_import: ClassVar[re.Pattern[str]] = re.compile(
        r"^(from|import)\s+pirn(_[a-z0-9_]+)?\b"
    )
    _file_suffixes: ClassVar[frozenset[str]] = frozenset(
        {
            "cfg",
            "csv",
            "db",
            "html",
            "ini",
            "json",
            "log",
            "md",
            "parquet",
            "sh",
            "sqlite",
            "toml",
            "txt",
            "yaml",
            "yml",
        }
    )

    def __init__(self, resolver: SourceImportResolver) -> None:
        self._resolver = resolver

    def audit(self, display: str, text: str) -> list[DocFinding]:
        """Every finding in ``text``, reported against the path ``display``."""
        blocks = MarkdownCodeBlocks.blocks(text)
        known_names = self._self_taught_classes(blocks)
        findings: list[DocFinding] = []
        for block in blocks:
            findings.extend(self._audit_block(display, block, known_names))
        for span in MarkdownCodeBlocks.inline_spans(text):
            findings.extend(self._audit_span(display, span, known_names))
        return findings

    def _self_taught_classes(self, blocks: list[FencedCodeBlock]) -> frozenset[str]:
        """Class names this document defines itself, in any of its own blocks.

        A tutorial that walks a reader through creating ``class Widget(Base): ...``
        is not asserting that ``Widget`` already ships in the repository — it is
        teaching the reader to write it. Importing that class later in the same
        document (a "recommended test structure", a "consumers import it like this")
        is reporting on the document's own worked example, not on repository state.
        """
        names: set[str] = set()
        for block in blocks:
            if block.tag and block.tag not in self._python_tags:
                continue
            source = block.source
            if block.tag == "pycon" or MarkdownCodeBlocks.is_transcript(source):
                source = MarkdownCodeBlocks.strip_prompts(source)
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            names.update(
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            )
        return frozenset(names)

    def _audit_span(
        self, display: str, span: InlineCodeSpan, known_names: frozenset[str]
    ) -> list[DocFinding]:
        if self._inline_import.match(span.text):
            try:
                tree = ast.parse(span.text)
            except SyntaxError:
                return []
            return [
                DocFinding(display, span.line, "doc_unresolved_import", detail)
                for node in self._pirn_imports(tree)
                for detail in self._unresolved(node, known_names)
            ]
        if self._is_quoted_string_literal(span.text):
            return []
        if not self._dotted.match(span.text):
            return []
        if span.text.rsplit(".", 1)[1] in self._file_suffixes:
            return []
        if self._resolver.resolves_path(span.text):
            return []
        detail = f"`{span.text}` does not resolve to a module, attribute or member"
        return [DocFinding(display, span.line, "doc_unresolved_path", detail)]

    @staticmethod
    def _is_quoted_string_literal(text: str) -> bool:
        """Whether ``text`` parses as a single Python string literal.

        ``"pirn.run_id"`` is a span quoting a *string value* — an OpenTelemetry
        attribute key, a filter expression, a config value — never a Python dotted
        path, however much it looks like one once the quotes are stripped. A bare
        ``pirn.run_id`` (no quotes) is still held to ``doc_unresolved_path``: quoting
        is exactly the signal that distinguishes "this is a string" from "this is
        code that names a real module".
        """
        try:
            node = ast.parse(text, mode="eval")
        except (SyntaxError, ValueError):
            return False
        return isinstance(node.body, ast.Constant) and isinstance(node.body.value, str)

    def _audit_block(
        self, display: str, block: FencedCodeBlock, known_names: frozenset[str]
    ) -> list[DocFinding]:
        tagged = block.tag in self._python_tags
        if block.tag and not tagged:
            return []
        source = block.source
        if block.tag == "pycon" or MarkdownCodeBlocks.is_transcript(source):
            source = MarkdownCodeBlocks.strip_prompts(source)
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            if not tagged:
                return []
            line = block.first_line + (error.lineno or 1) - 1
            return [DocFinding(display, line, "doc_code_block_syntax", str(error.msg))]
        imports = self._pirn_imports(tree)
        findings: list[DocFinding] = []
        for node in imports:
            line = block.first_line + node.lineno - 1
            findings.extend(
                DocFinding(display, line, "doc_unresolved_import", detail)
                for detail in self._unresolved(node, known_names)
            )
        return findings

    def _pirn_imports(self, tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
        found: list[ast.Import | ast.ImportFrom] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module is not None:
                    if self._resolver.is_pirn_root(node.module.split(".")[0]):
                        found.append(node)
            elif isinstance(node, ast.Import):
                if any(
                    self._resolver.is_pirn_root(a.name.split(".")[0])
                    for a in node.names
                ):
                    found.append(node)
        return sorted(found, key=attrgetter("lineno"))

    def _unresolved(
        self, node: ast.Import | ast.ImportFrom, known_names: frozenset[str]
    ) -> list[str]:
        if isinstance(node, ast.Import):
            return [
                f"module `{alias.name}` not found"
                for alias in node.names
                if self._resolver.is_pirn_root(alias.name.split(".")[0])
                and self._resolver.module_file(alias.name) is None
            ]
        module = node.module or ""
        names = [alias.name for alias in node.names if alias.name != "*"]
        if self._resolver.module_file(module) is None:
            if names and all(name in known_names for name in names):
                return []
            return [f"module `{module}` not found"]
        return [
            f"`{name}` not found in `{module}`"
            for name in names
            if name not in known_names and not self._resolver.has_name(module, name)
        ]
