"""``AstShapes`` — small, reusable readings of Python AST nodes shared by the gates."""

from __future__ import annotations

import ast
from collections.abc import Iterator


class AstShapes:
    """Stateless helpers over ``ast`` nodes."""

    @staticmethod
    def dotted_name(node: ast.expr) -> str:
        """``a.b.c`` for a ``Name``/``Attribute`` chain (subscripts unwrapped), else ``""``."""
        if isinstance(node, ast.Subscript):
            return AstShapes.dotted_name(node.value)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            head = AstShapes.dotted_name(node.value)
            return f"{head}.{node.attr}" if head else ""
        return ""

    @staticmethod
    def root_name(node: ast.expr) -> str | None:
        """``a`` for ``a``/``a.b.c``; ``None`` when the chain is not rooted at a name."""
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    @staticmethod
    def chain_root(node: ast.expr) -> ast.expr:
        """The innermost value of an ``Attribute``/``Subscript``/``Call`` chain."""
        while True:
            if isinstance(node, (ast.Attribute, ast.Subscript)):
                node = node.value
            elif isinstance(node, ast.Call):
                node = node.func
            else:
                return node

    @staticmethod
    def is_dunder(name: str) -> bool:
        return len(name) > 4 and name.startswith("__") and name.endswith("__")

    @staticmethod
    def is_docstring_stmt(stmt: ast.stmt) -> bool:
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )

    @staticmethod
    def without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        if body and AstShapes.is_docstring_stmt(body[0]):
            return body[1:]
        return body

    @staticmethod
    def alnum_lower(text: str) -> str:
        return "".join(ch.lower() for ch in text if ch.isalnum())

    @staticmethod
    def decorator_expr(decorator: ast.expr) -> ast.expr:
        return decorator.func if isinstance(decorator, ast.Call) else decorator

    @staticmethod
    def find_method(
        class_node: ast.ClassDef, name: str
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        for stmt in class_node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
                return stmt
        return None

    @staticmethod
    def module_scope_statements(body: list[ast.stmt]) -> list[ast.stmt]:
        """Statements that execute at module scope, descending into every compound block.

        ``if``/``try``/``for``/``while``/``with``/``match`` bodies run at module scope
        too, so a name bound inside one is a module-scope binding. Function and class
        bodies are not descended into.
        """
        statements: list[ast.stmt] = []
        for stmt in body:
            statements.append(stmt)
            for block in AstShapes.nested_blocks(stmt):
                statements.extend(AstShapes.module_scope_statements(block))
        return statements

    @staticmethod
    def nested_blocks(stmt: ast.stmt) -> Iterator[list[ast.stmt]]:
        """The statement lists a compound (non-def) statement executes in its own scope."""
        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            yield stmt.body
            yield stmt.orelse
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            yield stmt.body
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            yield stmt.body
            for handler in stmt.handlers:
                yield handler.body
            yield stmt.orelse
            yield stmt.finalbody
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                yield case.body

    @staticmethod
    def assignment_targets(stmt: ast.stmt) -> list[ast.expr]:
        """Every target expression bound by an assignment statement (tuples flattened)."""
        raw: list[ast.expr] = []
        if isinstance(stmt, ast.Assign):
            raw = list(stmt.targets)
        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
            raw = [stmt.target]
        flat: list[ast.expr] = []
        while raw:
            target = raw.pop(0)
            if isinstance(target, (ast.Tuple, ast.List)):
                raw = [*target.elts, *raw]
            elif isinstance(target, ast.Starred):
                raw = [target.value, *raw]
            else:
                flat.append(target)
        return flat

    @staticmethod
    def assigned_value(stmt: ast.stmt) -> ast.expr | None:
        if isinstance(stmt, (ast.Assign, ast.AugAssign)):
            return stmt.value
        if isinstance(stmt, ast.AnnAssign):
            return stmt.value
        return None
