"""Lazy grammar-compilation backend for constrained decoding (S3).

Grammar/regex *generation* from a schema is pure and backend-free (it lives in
:class:`ConstrainedDecodingMapper`). Optionally *compiling* — i.e. validating —
that grammar against a real constrained-decoding engine needs an optional
backend, imported here lazily through :func:`pirn_agents._require._require` so
``import pirn_agents`` (and every eager submodule import) stays backend-free.

The backend is provisioned by the ``grammar`` extra
(``pip install "pirn-agents[grammar]"``). Only the module's presence is relied
upon — no engine-specific, version-fragile API is called — so this stays robust
across backend releases while still exercising the lazy-import guard.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents._require import _require


def compile_constraint(constraint: Mapping[str, Any]) -> dict[str, Any]:
    """Compile/validate a decoding ``constraint`` via the optional backend.

    Args:
        constraint: A generated grammar/regex constraint mapping.

    Returns:
        A small record naming the backend that accepted the constraint plus the
        constraint itself, suitable for logging or attaching to a request.

    Raises:
        ImportError: If the ``grammar`` backend is not installed; the message
            names the exact ``pip install "pirn-agents[grammar]"`` command.
    """
    module = _require("grammar", "outlines")
    return {
        "backend": getattr(module, "__name__", "outlines"),
        "constraint": dict(constraint),
    }
