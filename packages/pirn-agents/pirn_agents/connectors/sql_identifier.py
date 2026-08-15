"""``SqlIdentifier`` — a validated, portably-quoted SQL identifier (PIR-722).

**Why this class exists.** Values in SQL are bound as parameters; *identifiers*
(table and column names) cannot be — no dialect provides a placeholder for them.
Anything that binds a table name into a statement therefore performs string
interpolation, which is exactly the shape of a SQL-injection vector. This class
is the one place that interpolation is allowed to happen, so the decision is
made once, documented, and tested rather than re-improvised per call site.

**The decision: validate against a portable allowlist, then quote.** Both halves
are load-bearing, and neither is sufficient alone.

*Validate.* Each dot-separated part must match ``[A-Za-z_][A-Za-z0-9_]*`` — the
unquoted-identifier grammar common to SQL:1999, SQLite, Postgres, MySQL and SQL
Server. Rejection happens at construction, so a hostile name fails fast at the
point of configuration instead of at query time. The allowlist excludes every
character that could terminate a quoted region or start a new token: ``"``,
``'``, ``` ` ```, ``[``, ``]``, ``;``, ``-``, ``/``, ``*``, ``%``, ``\\``,
parentheses, whitespace, NUL, and all non-ASCII (which would otherwise admit
homoglyph and zero-width confusables). At most two parts are accepted —
``schema.table``, covering SQLite's ``main.t`` and Postgres' ``public.t``.

*Quote.* Each validated part is wrapped in ``"`` and joined with ``.``. Quoting
is not the injection defence here — validation already guarantees no part can
escape — it is what keeps an identifier that collides with a reserved word
(``"order"``, ``"select"``) legal, and what preserves case, since an unquoted
identifier is case-folded (down in Postgres, up in Oracle) while a quoted one is
taken literally.

**Why not escape instead of validate?** Escaping by doubling embedded quotes is
dialect-sensitive: double quotes delimit identifiers under the SQL standard,
SQLite and Postgres, but MySQL uses backticks unless ``ANSI_QUOTES`` is set, and
SQL Server uses brackets. A facade that only escaped would be safe on the
dialects it was written against and unsafe on a backend plugged in later behind
the same interface. Restricting to the character set that needs no escaping in
*any* mainstream dialect makes the rendering correct regardless of which backend
the connector actually talks to. The cost is that exotic-but-legal identifiers
(spaces, non-ASCII, embedded quotes) are refused; a caller holding one should
create a view with a portable name rather than widen this class.

Errors deliberately name the offending *position* and never replay the rejected
text, because a rejected identifier can be attacker-controlled and the message
lands in logs.
"""

from __future__ import annotations

import re
from re import Pattern
from typing import ClassVar


class SqlIdentifier:
    """A SQL table/column identifier validated against a portable allowlist.

    Instances are immutable. Validation happens once, at construction, so any
    later write to the state ``sql`` is built from would bypass the allowlist
    entirely — rebinding ``_parts`` on a cleanly-constructed instance used to
    re-inject. Immutability is enforced two ways, deliberately: ``__slots__``
    means there is no instance ``__dict__`` and so no arbitrary attribute can be
    attached, and ``__setattr__``/``__delattr__`` refuse writes so an attempted
    mutation fails loudly instead of silently doing nothing. ``__init__`` seeds
    the slots through ``object.__setattr__``, which is the same mechanism a
    frozen dataclass generates; a frozen dataclass was not used directly because
    the public constructor takes raw text and stores validated *derived* state,
    which a generated ``__init__`` cannot express.
    """

    __slots__ = ("_parts", "_text")

    _parts: tuple[str, ...]
    _text: str

    # One whole identifier: a part, optionally followed by a dotted second part.
    # Matching the *whole* input in one pass is what keeps validation and
    # rendering reading the same text — see __init__ for why that matters.
    _pattern: ClassVar[Pattern[str]] = re.compile(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?"
    )
    _dot: ClassVar[Pattern[str]] = re.compile(r"\.")

    def __init__(self, raw: str) -> None:
        """Validate ``raw`` and retain the validated text for quoted rendering.

        ``isinstance(raw, str)`` admits *subclasses*, and a subclass may override
        any ``str`` method. That is not hypothetical: a subclass whose ``split``
        returns itself and whose ``__format__`` returns an injection defeated a
        validate-then-quote implementation that split the input and interpolated
        the resulting objects, because ``re`` reads the honest underlying buffer
        while the f-string called the lying ``__format__``.

        The invariant that closes this is that **the text which is validated is
        exactly the text which is quoted**. Validation matches the whole input
        with a regex — which reads the buffer, not the object's methods — and
        everything downstream is derived from ``match.group()``, which CPython
        returns as an exact ``str`` regardless of the input's class. No method or
        dunder of the caller's object is consulted after that point.

        Args:
            raw: An unquoted identifier, optionally ``schema``-qualified with a
                single dot (e.g. ``"users"`` or ``"public.users"``).

        Raises:
            TypeError: If ``raw`` is not a ``str``.
            ValueError: If ``raw`` has more than two dot-separated parts, or any
                part is not a portable unquoted SQL identifier.
        """
        if not isinstance(raw, str):
            raise TypeError(f"SqlIdentifier: identifier must be a str, got {type(raw).__name__}")
        match = self._pattern.fullmatch(raw)
        if match is None:
            # Count parts with a regex too: str.split on a subclass is the
            # caller's code, and the count reaches the message below.
            seen = len(self._dot.split(raw))
            if seen > 2:
                raise ValueError(
                    "SqlIdentifier: expected at most a 'schema.name' identifier, "
                    f"got {seen} dot-separated parts"
                )
            raise ValueError(
                "SqlIdentifier: not a portable SQL identifier; each dot-separated part "
                "must match [A-Za-z_][A-Za-z0-9_]* (ASCII letters, digits and underscore, "
                "not starting with a digit)"
            )
        text = match.group()
        # object.__setattr__ because this class's own __setattr__ refuses writes.
        object.__setattr__(self, "_parts", tuple(text.split(".")))
        object.__setattr__(self, "_text", text)

    def __setattr__(self, name: str, value: object) -> None:
        """Refuse every attribute write: the validated state is final."""
        raise AttributeError(
            f"SqlIdentifier is immutable; cannot set {name!r}. Its state is validated "
            "once at construction, so rebinding it would bypass the allowlist. "
            "Construct a new SqlIdentifier instead."
        )

    def __delattr__(self, name: str) -> None:
        """Refuse every attribute deletion, for the same reason as ``__setattr__``."""
        raise AttributeError(f"SqlIdentifier is immutable; cannot delete {name!r}")

    @property
    def sql(self) -> str:
        """Return the double-quoted, dot-joined form safe to interpolate into SQL."""
        return ".".join(f'"{part}"' for part in self._parts)

    @property
    def text(self) -> str:
        """Return the validated identifier as a plain ``str``.

        This is the text the allowlist actually accepted, never the object the
        caller passed: returning a ``str`` subclass would hand a downstream
        interpolation site the same lying ``__format__`` this class exists to
        defuse. It is unquoted, so a caller embedding it in SQL must quote it —
        prefer :attr:`sql`, which is already safe to interpolate.
        """
        return self._text

    def __repr__(self) -> str:
        """Return an unambiguous representation naming the validated identifier."""
        return f"SqlIdentifier({self._text!r})"
