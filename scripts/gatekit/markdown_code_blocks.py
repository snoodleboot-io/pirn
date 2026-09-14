"""Extract fenced code blocks and inline code spans from markdown text."""

from __future__ import annotations

import re
import textwrap
from typing import ClassVar

from gatekit.fenced_code_block import FencedCodeBlock
from gatekit.inline_code_span import InlineCodeSpan


class MarkdownCodeBlocks:
    """Split markdown into fenced blocks (with tags) and inline spans outside fences."""

    _opener: ClassVar[re.Pattern[str]] = re.compile(r"^\s*(`{3,}|~{3,})\s*([^\s`{]*)")
    _span: ClassVar[re.Pattern[str]] = re.compile(r"(`+)([^`]+?)\1")
    _prompt: ClassVar[re.Pattern[str]] = re.compile(r"^(>>>|\.\.\.)( |$)")

    @classmethod
    def blocks(cls, text: str) -> list[FencedCodeBlock]:
        """Every fenced block, with its tag lower-cased (``""`` when untagged)."""
        found: list[FencedCodeBlock] = []
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            match = cls._opener.match(lines[index])
            if match is None:
                index += 1
                continue
            fence = match.group(1)
            body_start = index + 1
            end = body_start
            while end < len(lines) and not cls._closes(lines[end], fence):
                end += 1
            body = textwrap.dedent("\n".join(lines[body_start:end]))
            tag = match.group(2).lower()
            found.append(
                FencedCodeBlock(tag=tag, first_line=body_start + 1, source=body)
            )
            index = end + 1
        return found

    @classmethod
    def inline_spans(cls, text: str) -> list[InlineCodeSpan]:
        """Every backtick code span on a line that is not inside a fenced block."""
        spans: list[InlineCodeSpan] = []
        fence: str | None = None
        for number, line in enumerate(text.splitlines(), start=1):
            if fence is not None:
                if cls._closes(line, fence):
                    fence = None
                continue
            match = cls._opener.match(line)
            if match is not None:
                fence = match.group(1)
                continue
            for span in cls._span.finditer(line):
                spans.append(InlineCodeSpan(line=number, text=span.group(2).strip()))
        return spans

    @classmethod
    def strip_prompts(cls, source: str) -> str:
        """Turn a pycon transcript into code, blanking output lines to keep line numbers."""
        kept: list[str] = []
        for line in source.splitlines():
            match = cls._prompt.match(line)
            kept.append(line[match.end() :] if match is not None else "")
        return "\n".join(kept)

    @staticmethod
    def is_transcript(source: str) -> bool:
        """Whether the first non-blank line of ``source`` is a ``>>>`` prompt."""
        for line in source.splitlines():
            if line.strip():
                return line.startswith(">>>")
        return False

    @staticmethod
    def _closes(line: str, fence: str) -> bool:
        stripped = line.strip()
        return len(stripped) >= len(fence) and set(stripped) == {fence[0]}
