"""``DefinitionReference`` — a process-independent name for a function or class.

Content identity (PIR-840) names *where a tool's behaviour is defined* so that two
processes loading the same definition hash equal. A name is only an identity if it
picks out exactly one definition, and several ordinary Python constructs share a
qualname across definitions that behave differently:

* a class or function built inside a factory (``make.<locals>.Scaled``), one per call;
* a lambda (``<lambda>``);
* a definition later shadowed by another of the same name in the same module;
* two different scripts, each loaded as ``__main__``.

:meth:`DefinitionReference.of` returns ``None`` for all of these, and callers treat
``None`` as "stay identity-keyed". A ``__main__`` definition is named by the resolved
absolute path of the running script, so a different script refuses; a ``__main__``
with no file (a REPL, a notebook, ``python -c``) has nothing to name it by.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path


class DefinitionReference:
    """Resolve a stable ``module.qualname`` for a definition, or ``None`` if it has none."""

    @staticmethod
    def of(
        target: type | Callable[..., object],
        *,
        unwrap_binding: Callable[[object], object] | None = None,
    ) -> str | None:
        """Return the reference for ``target``, or ``None`` when no name is unique to it.

        Args:
            target: A class or plain function.
            unwrap_binding: Maps the object the module binds at ``qualname`` to the
                definition it stands for, e.g. a ``@tool`` rebinding a function's
                name to the tool wrapping it. Defaults to the identity.

        Returns:
            ``"<module>.<qualname>"``, with ``__main__`` written as
            ``"__main__[<absolute script path>]"``; or ``None`` when the qualname is
            local or a lambda, the module is not loaded, the module does not bind
            ``qualname`` back to ``target``, or ``__main__`` has no script file.
        """
        qualname = target.__qualname__
        if "<" in qualname:
            return None
        module_name = target.__module__
        module = sys.modules.get(module_name)
        if module is None:
            return None
        bound: object = module
        for part in qualname.split("."):
            bound = vars(bound).get(part) if hasattr(bound, "__dict__") else None
            if bound is None:
                return None
        if unwrap_binding is not None:
            bound = unwrap_binding(bound)
        if bound is not target:
            return None
        if module_name != "__main__":
            return f"{module_name}.{qualname}"
        script = vars(module).get("__file__")
        if not isinstance(script, str):
            return None
        return f"__main__[{Path(script).resolve()}].{qualname}"
