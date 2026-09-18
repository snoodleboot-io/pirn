"""``RequiredEngine`` — an optional engine a knot needs at run time, checked at construction.

A knot built on an optional engine (pandas, Polars, DuckDB, ...) imports it
inside ``process()``. Without a declaration, a missing engine surfaces only when
the knot first runs — mid-pipeline, possibly hours in. ``Knot._required_engines``
lists the engines the knot cannot run without; ``Knot`` imports each one through
:meth:`OptionalDependency.require
<pirn.core.optional_dependency.OptionalDependency.require>` on the class's first
construction (never at module import) and caches the success per class, so a
missing engine raises the owning package's install hint when the pipeline is
built.

This is deliberately separate from ``Knot._annotation_imports``
(:class:`~pirn.core.annotation_import.AnnotationImport`), which binds names that
``process()``'s *annotations* use. An engine a knot only calls at run time is a
requirement, not an annotation name.

Algorithm:
    1. ``OptionalDependency.require(module, extra=extra, package=package)``.
    2. Return the imported module.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from pirn.core.optional_dependency import OptionalDependency


@dataclass(frozen=True)
class RequiredEngine:
    """An importable module a knot needs at run time, and the extra that installs it.

    Attributes:
        module: Dotted module to import (``"pandas"``, ``"ray.data"``).
        extra: The optional-dependency extra of ``package`` that installs ``module``.
        package: The distribution that declares ``extra``.
    """

    module: str
    extra: str
    package: str = "pirn-core"

    def __post_init__(self) -> None:
        for name, value in (
            ("module", self.module),
            ("extra", self.extra),
            ("package", self.package),
        ):
            if not isinstance(value, str):
                raise TypeError(f"RequiredEngine: {name} must be a str, got {type(value).__name__}")
            if not value:
                raise ValueError(f"RequiredEngine: {name} must be a non-empty str")

    def require(self) -> ModuleType:
        """Import the module, raising the install hint when it is missing.

        Returns:
            The imported module.

        Raises:
            ImportError: If ``module`` is not installed; the message names
                ``pip install "<package>[<extra>]"``.
        """
        return OptionalDependency.require(self.module, extra=self.extra, package=self.package)
