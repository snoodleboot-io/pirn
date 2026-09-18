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
    is not a dotted path and is not checked.
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
        findings: list[DocFinding] = []
        for block in MarkdownCodeBlocks.blocks(text):
            findings.extend(self._audit_block(display, block))
        for span in MarkdownCodeBlocks.inline_spans(text):
            findings.extend(self._audit_span(display, span))
        return findings

    def _audit_span(self, display: str, span: InlineCodeSpan) -> list[DocFinding]:
        if self._inline_import.match(span.text):
            try:
                tree = ast.parse(span.text)
            except SyntaxError:
                return []
            return [
                DocFinding(display, span.line, "doc_unresolved_import", detail)
                for node in self._pirn_imports(tree)
                for detail in self._unresolved(node)
            ]
        if not self._dotted.match(span.text):
            return []
        if span.text.rsplit(".", 1)[1] in self._file_suffixes:
            return []
        if self._resolver.resolves_path(span.text):
            return []
        detail = f"`{span.text}` does not resolve to a module, attribute or member"
        return [DocFinding(display, span.line, "doc_unresolved_path", detail)]

    def _audit_block(self, display: str, block: FencedCodeBlock) -> list[DocFinding]:
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
                for detail in self._unresolved(node)
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

    def _unresolved(self, node: ast.Import | ast.ImportFrom) -> list[str]:
        if isinstance(node, ast.Import):
            return [
                f"module `{alias.name}` not found"
                for alias in node.names
                if self._resolver.is_pirn_root(alias.name.split(".")[0])
                and self._resolver.module_file(alias.name) is None
            ]
        module = node.module or ""
        if self._resolver.module_file(module) is None:
            return [f"module `{module}` not found"]
        return [
            f"`{alias.name}` not found in `{module}`"
            for alias in node.names
            if alias.name != "*" and not self._resolver.has_name(module, alias.name)
        ]
