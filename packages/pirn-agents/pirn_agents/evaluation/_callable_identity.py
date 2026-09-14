"""``_CallableIdentity`` — a content identity for a callable, for replay guards.

An eval run's target and metrics are callables, and a callable is not a value
``content_hash`` can canonicalise: it collapses to a shared
``sha256:unhashable:<type>`` sentinel. Identifying one by name alone
(``module.qualname``) would let an edited function body under the same name
replay a stale recording. This class derives the identity from what the
callable *does* wherever Python exposes it.

Algorithm:
    ``of(candidate)`` returns a JSON-shaped canonical form:

    1. ``functools.partial`` — the wrapped callable's identity plus the
       content hashes of its bound positional and keyword arguments.
    2. Bound method — the underlying function's identity plus the content
       hash of the object it is bound to.
    3. Python function (including a lambda and an ``async def``) — its
       qualified name, its code identity, the content hashes of its defaults
       and keyword-only defaults, and the identity of every closure cell's
       value (a function-valued cell is identified recursively; anything else
       by ``content_hash``; an empty cell as ``None``).
    4. Code identity — the bytecode, the names and local/free/cell variable
       names it uses, and its constants, each nested code object identified
       recursively (so an inner function or comprehension body counts) and
       every other constant by ``content_hash``. Line-number tables are left
       out on purpose: moving a function does not change what it computes.
    5. An object whose type defines a Python ``__call__`` — that method's
       function identity plus the object's content hash.
    6. Anything else (a C builtin, a callable with no inspectable code) —
       its ``module.qualname`` only. This fallback cannot see an edit and is
       documented on ``RunEval.run``.

    Recursion through closure cells is cycle-safe: a function already being
    identified further up the chain is named, not re-entered.

Internal API.
"""

from __future__ import annotations

import functools
import inspect
import types
from typing import Any

from pirn.core.hashing import content_hash


class _CallableIdentity:
    """Derive a stable, content-based canonical form for a callable."""

    @staticmethod
    def of(candidate: object) -> Any:
        """Return the canonical identity of ``candidate`` (see the module docstring)."""
        return _CallableIdentity._identify(candidate, frozenset())

    @staticmethod
    def _name(candidate: object) -> str:
        """``module.qualname`` of ``candidate``, or of its type when it has none."""
        module = getattr(candidate, "__module__", None)
        qualname = getattr(candidate, "__qualname__", None)
        if not isinstance(module, str) or not isinstance(qualname, str):
            module = type(candidate).__module__
            qualname = type(candidate).__qualname__
        return f"{module}.{qualname}"

    @staticmethod
    def _identify(candidate: object, active: frozenset[int]) -> Any:
        if isinstance(candidate, functools.partial):
            bound: functools.partial[Any] = candidate
            return {
                "partial": _CallableIdentity._identify(bound.func, active),
                "args": [content_hash(arg) for arg in bound.args],
                "keywords": {
                    key: content_hash(value) for key, value in sorted(bound.keywords.items())
                },
            }
        if isinstance(candidate, types.MethodType):
            return {
                "method": _CallableIdentity._identify(candidate.__func__, active),
                "self": content_hash(candidate.__self__),
            }
        if isinstance(candidate, types.FunctionType):
            return _CallableIdentity._function(candidate, active)
        call = inspect.getattr_static(type(candidate), "__call__", None)
        if isinstance(call, types.FunctionType):
            return {
                "callable_object": _CallableIdentity._name(type(candidate)),
                "call": _CallableIdentity._function(call, active),
                "state": content_hash(candidate),
            }
        return {"name": _CallableIdentity._name(candidate)}

    @staticmethod
    def _function(function: types.FunctionType, active: frozenset[int]) -> Any:
        name = _CallableIdentity._name(function)
        if id(function) in active:
            return {"recursive": name}
        inner = active | {id(function)}
        cells: list[Any] = []
        for cell in function.__closure__ or ():
            try:
                value: object = cell.cell_contents
            except ValueError:
                cells.append(None)
                continue
            if isinstance(value, (types.FunctionType, types.MethodType, functools.partial)):
                cells.append(_CallableIdentity._identify(value, inner))
            else:
                cells.append(content_hash(value))
        return {
            "function": name,
            "code": _CallableIdentity._code(function.__code__),
            "defaults": content_hash(function.__defaults__),
            "kwdefaults": content_hash(function.__kwdefaults__),
            "closure": cells,
        }

    @staticmethod
    def _code(code: types.CodeType) -> Any:
        return {
            "bytecode": code.co_code.hex(),
            "names": list(code.co_names),
            "varnames": list(code.co_varnames),
            "freevars": list(code.co_freevars),
            "cellvars": list(code.co_cellvars),
            "flags": code.co_flags,
            "consts": [_CallableIdentity._constant(const) for const in code.co_consts],
        }

    @staticmethod
    def _constant(const: object) -> Any:
        if isinstance(const, types.CodeType):
            return _CallableIdentity._code(const)
        if isinstance(const, tuple):
            return {"tuple": [_CallableIdentity._constant(item) for item in const]}
        return content_hash(const)
