#!/usr/bin/env python3
"""Reject documentation whose Python code or pirn import paths do not resolve.

Docs rot silently: a renamed class keeps being taught by every AGENTIC_USE.md and
README that quoted it. This gate reads each markdown file and checks, statically
against the repository source (nothing is imported):

* ``doc_code_block_syntax`` — every fenced block tagged ``python``/``py``/``pycon``
  parses (pycon ``>>> `` / ``... `` prompts are stripped first).
* ``doc_unresolved_import`` — every ``import pirn...`` / ``from pirn_<x>... import A``
  in such a block (or in an untagged block that parses and imports pirn) names a
  module under ``packages/<dist>/<root>/`` and top-level names that module defines.
* ``doc_unresolved_path`` — every inline code span that is a dotted ``pirn.`` /
  ``pirn_<x>.`` path names a module, a module attribute, or a class member.

CLI contract
------------
Arguments are markdown files or directories (walked for ``*.md``, skipping
``.venv``, ``node_modules``, ``site``, ``__pycache__`` and ``CHANGELOG.md``).

* ``0`` — files were checked and nothing is stale.
* ``1`` — findings, printed as ``path:line: [rule] detail``.
* ``2`` — unusable invocation: no arguments, a nonexistent path, or paths that
  match zero markdown files. A gate that checked nothing must never pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gatekit.doc_import_auditor import DocImportAuditor
from gatekit.markdown_file_collector import MarkdownFileCollector
from gatekit.source_import_resolver import SourceImportResolver


class CheckDocImports:
    """Command-line entry point for the documentation import gate."""

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        """Check the markdown named by ``argv``; return the process exit code."""
        arguments = sys.argv[1:] if argv is None else argv
        try:
            files = MarkdownFileCollector.collect(arguments)
        except ValueError as error:
            print(f"check_doc_imports: {error}", file=sys.stderr)
            return 2
        auditor = DocImportAuditor(
            SourceImportResolver(Path(__file__).resolve().parents[1])
        )
        count = 0
        for path in files:
            for finding in auditor.audit(str(path), path.read_text(encoding="utf-8")):
                print(finding.render())
                count += 1
        if count:
            print(f"check_doc_imports: {count} finding(s) in {len(files)} file(s)")
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(CheckDocImports.main())
