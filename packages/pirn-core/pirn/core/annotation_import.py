"""``AnnotationImport`` — a name a knot's annotations use, imported only when hints resolve.

A knot built on an optional engine (pandas, Polars, DuckDB, ...) imports the
engine only under ``if TYPE_CHECKING:``, so importing the knot's module — and the
registry walk every ``import pirn_<pkg>`` performs — never loads it. ``Knot``
still resolves ``process()``'s annotations at runtime to build its validation
adapters, so every name those annotations use must be importable at that moment.
The knot declares each such name in ``Knot._annotation_imports`` as an
``AnnotationImport``; ``Knot`` resolves the whole mapping the first time a
class's hints are needed (its first construction, or ``input_annotations()``),
never at module import, and caches the result per class.

Resolution goes through :meth:`OptionalDependency.require
<pirn.core.optional_dependency.OptionalDependency.require>`, so a missing engine
raises the owning package's real install hint at construction instead of a
``NameError`` deep inside ``typing.get_type_hints``.

Algorithm:
    1. ``OptionalDependency.require(module, extra=extra, package=package)``.
    2. Return the module itself, or its ``attribute`` when one is named.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.optional_dependency import OptionalDependency


@dataclass(frozen=True)
class AnnotationImport:
    """Where one annotation name comes from, and the extra that installs it.

    Attributes:
        module: Dotted module to import (``"pandas"``, ``"pyarrow.compute"``).
        extra: The optional-dependency extra of ``package`` that installs ``module``.
        package: The distribution that declares ``extra``.
        attribute: An attribute of ``module`` to bind instead of the module
            itself (``"DataFrame"`` for ``from pandas import DataFrame``), or
            ``None`` to bind the module.
    """

    module: str
    extra: str
    package: str = "pirn-core"
    attribute: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("module", self.module),
            ("extra", self.extra),
            ("package", self.package),
        ):
            if not isinstance(value, str):
                raise TypeError(
                    f"AnnotationImport: {name} must be a str, got {type(value).__name__}"
                )
            if not value:
                raise ValueError(f"AnnotationImport: {name} must be a non-empty str")
        if self.attribute is not None:
            if not isinstance(self.attribute, str):
                raise TypeError(
                    f"AnnotationImport: attribute must be a str or None, got {type(self.attribute).__name__}"
                )
            if not self.attribute:
                raise ValueError("AnnotationImport: attribute must be a non-empty str or None")

    def resolve(self) -> Any:
        """Import the module (raising the install hint when it is missing) and return the bound object.

        Returns:
            The module, or its ``attribute``.

        Raises:
            ImportError: If ``module`` is not installed; the message names
                ``pip install "<package>[<extra>]"``.
            AttributeError: If ``module`` has no ``attribute``.
        """
        module = OptionalDependency.require(self.module, extra=self.extra, package=self.package)
        if self.attribute is None:
            return module
        # A name bound by string is inherently dynamic: this is the framework seam
        # that turns a declared import into the object the annotation names.
        return getattr(module, self.attribute)
