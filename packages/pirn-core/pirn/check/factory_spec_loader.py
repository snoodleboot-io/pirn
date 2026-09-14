"""``FactorySpecLoader`` — resolve the ``tapestry-check`` ``MODULE:FUNCTION`` spec."""

from __future__ import annotations

import importlib
import sys
from typing import Any


class FactorySpecLoader:
    """Resolve a ``MODULE:FUNCTION`` spec string to the callable it names."""

    @staticmethod
    def load_factory(spec: str) -> Any:
        """Import ``module:function`` and return the callable."""
        if ":" not in spec:
            print(
                f"error: expected MODULE:FUNCTION, got {spec!r}\nexample: mymodule:build_tapestry",
                file=sys.stderr,
            )
            sys.exit(2)

        module_path, func_name = spec.rsplit(":", 1)
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            print(f"error: cannot import {module_path!r}: {exc}", file=sys.stderr)
            sys.exit(2)

        func = getattr(module, func_name, None)
        if func is None:
            print(
                f"error: {module_path!r} has no attribute {func_name!r}",
                file=sys.stderr,
            )
            sys.exit(2)
        return func
