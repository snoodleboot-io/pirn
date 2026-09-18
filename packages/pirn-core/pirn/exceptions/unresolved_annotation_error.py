"""Raised when a knot's ``process()`` type hints cannot be resolved."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UnresolvedAnnotationError(PirnError, TypeError):
    """A knot class's ``process()`` annotations could not be resolved to types.

    ``Knot`` builds its input and output ``TypeAdapter``s — and finds its
    ``Knot | T`` scalar-coercion candidates — from ``typing.get_type_hints``
    over ``process()``.  A hint that cannot be resolved (a name imported only
    under ``if TYPE_CHECKING:`` and missing from ``_annotation_imports``, a
    forward reference to a name that never came into scope) used to warn and
    return no hints, which silently disabled validation and coercion for every
    instance of the class: ``KnotConfig.validate_io`` read as on while nothing
    was ever checked, and a scalar wired where a ``Knot | T`` was declared
    never became a ``Parameter`` node.  A knot whose declared types cannot
    resolve is broken, so construction raises this instead (PIR-873).

    Attributes:
        knot_class: Name of the knot class whose hints failed to resolve.
    """

    def __init__(self, *, knot_class: str, cause: BaseException) -> None:
        """Name the class and the resolution failure underneath it.

        Args:
            knot_class: ``cls.__name__`` of the knot whose hints failed.
            cause: The exception ``get_type_hints`` raised.
        """
        self._knot_class = knot_class
        super().__init__(
            f"{knot_class}.process: type hints could not be resolved ({cause!r}). "
            "A knot whose declared types cannot resolve cannot be validated. "
            "This usually means a forward-referenced annotation is out of scope "
            "-- e.g. a name imported only under 'if TYPE_CHECKING:' and missing "
            "from the class's _annotation_imports."
        )

    @property
    def knot_class(self) -> str:
        """Name of the knot class whose ``process()`` hints failed to resolve."""
        return self._knot_class
