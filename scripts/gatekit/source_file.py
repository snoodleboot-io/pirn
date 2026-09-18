"""``SourceFile`` — one parsed Python file plus the facts every gate needs about it."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path


class SourceFile:
    """A Python file read, tokenized and parsed once.

    ``module_name`` is the dotted import name the file has relative to the outermost
    directory of its ``__init__.py`` chain; ``scope`` is the directory that name is
    relative to. Files under a workspace import root (``packages/<dist>/pirn*``) are
    *global* modules, addressed by their bare dotted name; every other file (tests,
    examples, scripts) is addressed within its scope, so ``tests.helpers`` in two
    packages never collide.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.source = path.read_text(encoding="utf-8")
        self.lines = self.source.splitlines()
        self.parse_error: str | None = None
        self.tree: ast.Module = ast.Module(body=[], type_ignores=[])
        try:
            self.tree = ast.parse(self.source, filename=str(path))
        except SyntaxError as exc:
            self.parse_error = f"file does not parse: {exc.msg} (line {exc.lineno})"
        self.comments: list[tuple[int, int, str]] = []
        if self.parse_error is None:
            for token in tokenize.generate_tokens(io.StringIO(self.source).readline):
                if token.type == tokenize.COMMENT:
                    self.comments.append((token.start[0], token.start[1], token.string))
        self.is_package_init = path.stem == "__init__"
        parts = [] if self.is_package_init else [path.stem]
        directory = path.parent.resolve()
        if not (directory / "__init__.py").is_file():
            parts = [path.stem]
        else:
            while (directory / "__init__.py").is_file():
                parts.insert(0, directory.name)
                directory = directory.parent
        self.scope = directory
        self.module_name = ".".join(parts)
        self.is_global = (
            bool(parts)
            and (parts[0] == "pirn" or parts[0].startswith("pirn_"))
            and directory.parent.name == "packages"
        )

    @property
    def module_key(self) -> str:
        """The index key: the dotted name for a global module, ``<scope>|<name>`` otherwise."""
        if self.is_global:
            return self.module_name
        return f"{self.scope}|{self.module_name}"

    @property
    def own_line_comment_lines(self) -> set[int]:
        """Line numbers holding only a comment (nothing but whitespace before the ``#``)."""
        found: set[int] = set()
        for lineno, col, _text in self.comments:
            if not self.lines[lineno - 1][:col].strip():
                found.add(lineno)
        return found

    def comment_on_line(self, lineno: int) -> str:
        return " ".join(text for line, _col, text in self.comments if line == lineno)
