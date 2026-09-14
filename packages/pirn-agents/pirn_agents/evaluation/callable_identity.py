"""``CallableIdentity`` — a content identity for a callable, for replay guards.

An eval run's target and metrics are callables, and a callable is not a value
``ContentHasher.hash`` can canonicalise: it collapses to a shared
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
       by ``ContentHasher.hash``; an empty cell as ``None``).
    4. Code identity — the bytecode, the names and local/free/cell variable
       names it uses, and its constants, each nested code object identified
       recursively (so an inner function or comprehension body counts) and
       every other constant by ``ContentHasher.hash``. Line-number tables are left
       out on purpose: moving a function does not change what it computes.
    5. An object whose type defines a Python ``__call__`` — that method's
       function identity plus the object's content hash.
    6. Anything else (a C builtin, a callable with no inspectable code) —
       its ``module.qualname`` only. This fallback cannot see an edit and is
       documented on ``RunEval.run``.

    Recursion through closure cells is cycle-safe: a function already being
    identified further up the chain is named, not re-entered.

Package-internal: used by :class:`~pirn_agents.evaluation.eval_subject.EvalSubject`.
"""

from __future__ import annotations

import functools
import inspect
import types
from typing import TypeGuard

from pirn.core.content_hasher import ContentHasher


class CallableIdentity:
    """Derive a stable, content-based canonical form for a callable.

    Every form is a JSON-shaped ``dict[str, object]`` whose leaves are ``str``
    content hashes, names, ``int`` code flags, ``None`` for an empty closure
    cell, and nested forms.
    """

    @staticmethod
    def of(candidate: object) -> dict[str, object]:
        """Return the canonical identity of ``candidate`` (see the module docstring)."""
        return CallableIdentity._identify(candidate, frozenset())

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
    def _is_partial(candidate: object) -> TypeGuard[functools.partial[object]]:
        """Whether ``candidate`` is a ``functools.partial`` (any result type)."""
        return isinstance(candidate, functools.partial)

    @staticmethod
    def _is_tuple(candidate: object) -> TypeGuard[tuple[object, ...]]:
        """Whether ``candidate`` is a ``tuple`` (any element types)."""
        return isinstance(candidate, tuple)

    @staticmethod
    def _identify(candidate: object, active: frozenset[int]) -> dict[str, object]:
        if CallableIdentity._is_partial(candidate):
            return {
                "partial": CallableIdentity._identify(candidate.func, active),
                "args": [ContentHasher.hash(arg) for arg in candidate.args],
                "keywords": {
                    key: ContentHasher.hash(value)
                    for key, value in sorted(candidate.keywords.items())
                },
            }
        if isinstance(candidate, types.MethodType):
            return {
                "method": CallableIdentity._identify(candidate.__func__, active),
                "self": ContentHasher.hash(candidate.__self__),
            }
        if isinstance(candidate, types.FunctionType):
            return CallableIdentity._function(candidate, active)
        call = inspect.getattr_static(type(candidate), "__call__", None)
        if isinstance(call, types.FunctionType):
            return {
                "callable_object": CallableIdentity._name(type(candidate)),
                "call": CallableIdentity._function(call, active),
                "state": ContentHasher.hash(candidate),
            }
        return {"name": CallableIdentity._name(candidate)}

    @staticmethod
    def _function(function: types.FunctionType, active: frozenset[int]) -> dict[str, object]:
        name = CallableIdentity._name(function)
        if id(function) in active:
            return {"recursive": name}
        inner = active | {id(function)}
        cells: list[dict[str, object] | str | None] = []
        for cell in function.__closure__ or ():
            try:
                value: object = cell.cell_contents
            except ValueError:
                cells.append(None)
                continue
            if CallableIdentity._is_partial(value) or isinstance(
                value, (types.FunctionType, types.MethodType)
            ):
                cells.append(CallableIdentity._identify(value, inner))
            else:
                cells.append(ContentHasher.hash(value))
        return {
            "function": name,
            "code": CallableIdentity._code(function.__code__),
            "defaults": ContentHasher.hash(function.__defaults__),
            "kwdefaults": ContentHasher.hash(function.__kwdefaults__),
            "closure": cells,
        }

    @staticmethod
    def _code(code: types.CodeType) -> dict[str, object]:
        return {
            "bytecode": code.co_code.hex(),
            "names": list(code.co_names),
            "varnames": list(code.co_varnames),
            "freevars": list(code.co_freevars),
            "cellvars": list(code.co_cellvars),
            "flags": code.co_flags,
            "consts": [CallableIdentity._constant(const) for const in code.co_consts],
        }

    @staticmethod
    def _constant(const: object) -> dict[str, object] | str:
        if isinstance(const, types.CodeType):
            return CallableIdentity._code(const)
        if CallableIdentity._is_tuple(const):
            return {"tuple": [CallableIdentity._constant(item) for item in const]}
        return ContentHasher.hash(const)
