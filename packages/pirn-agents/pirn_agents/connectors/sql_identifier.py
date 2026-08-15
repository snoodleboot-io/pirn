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


class SqlIdentifier:
    """A SQL table/column identifier validated against a portable allowlist."""

    def __init__(self, raw: str) -> None:
        """Validate ``raw`` and retain its parts for quoted rendering.

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
        pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
        parts = raw.split(".")
        if len(parts) > 2:
            raise ValueError(
                "SqlIdentifier: expected at most a 'schema.name' identifier, "
                f"got {len(parts)} dot-separated parts"
            )
        for position, part in enumerate(parts, start=1):
            if pattern.fullmatch(part) is None:
                raise ValueError(
                    f"SqlIdentifier: part {position} of {len(parts)} is not a portable SQL "
                    "identifier; each part must match [A-Za-z_][A-Za-z0-9_]* "
                    "(ASCII letters, digits and underscore, not starting with a digit)"
                )
        self._parts = tuple(parts)
        self._raw = raw

    @property
    def sql(self) -> str:
        """Return the double-quoted, dot-joined form safe to interpolate into SQL."""
        return ".".join(f'"{part}"' for part in self._parts)

    @property
    def text(self) -> str:
        """Return the original unquoted identifier as supplied."""
        return self._raw

    def __repr__(self) -> str:
        """Return an unambiguous representation naming the validated identifier."""
        return f"SqlIdentifier({self._raw!r})"
