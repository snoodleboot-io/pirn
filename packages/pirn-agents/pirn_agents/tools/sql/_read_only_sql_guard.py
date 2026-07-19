"""Read-only SQL statement guard for the ``sql_query`` tool.

:class:`ReadOnlySqlGuard` performs a conservative, dependency-free check that a
statement is a single read (``SELECT``/``WITH``) and contains no DML/DDL
keyword. String literals and comments are stripped before scanning so a keyword
inside a quoted value does not trigger a false positive. The forbidden-keyword
set is built once in the constructor rather than on every call.

**Scope of protection.** This is a best-effort syntactic guard, *not* a SQL
parser and *not* a substitute for a least-privilege, read-only database role.
For untrusted input, also connect with a database account that lacks write
permission. See ``pirn_agents/TOOLS.md``.
"""

from __future__ import annotations

import re

from pirn_agents.security.security_guard import SecurityGuard


class ReadOnlySqlGuard(SecurityGuard):
    """Reject any statement that is not a single read-only ``SELECT``/``WITH``."""

    def __init__(self) -> None:
        """Build the forbidden write/DDL keyword set once."""
        self._forbidden: frozenset[str] = frozenset(
            {
                "INSERT",
                "UPDATE",
                "DELETE",
                "DROP",
                "ALTER",
                "CREATE",
                "REPLACE",
                "TRUNCATE",
                "GRANT",
                "REVOKE",
                "ATTACH",
                "DETACH",
                "PRAGMA",
                "VACUUM",
                "MERGE",
                "UPSERT",
                "REINDEX",
            }
        )

    def assert_read_only(self, query: str) -> None:
        """Raise :class:`ValueError` unless ``query`` is a single read-only statement.

        Args:
            query: The SQL text to vet.

        Raises:
            ValueError: If ``query`` is empty, contains multiple statements, does
                not start with ``SELECT``/``WITH``, or contains a write/DDL
                keyword.
        """
        cleaned = self._strip_comments_and_strings(query).strip()
        if not cleaned:
            self._reject("sql_query: query is empty")
        statements = [s for s in cleaned.split(";") if s.strip()]
        if len(statements) > 1:
            self._reject("sql_query: multiple statements are not allowed in read-only mode")
        body = statements[0].strip()
        first = body.split()[0].upper()
        if first not in ("SELECT", "WITH"):
            self._reject(
                f"sql_query: only SELECT/WITH statements are allowed in read-only mode, "
                f"got {first!r}"
            )
        tokens = {t.upper() for t in re.findall(r"[A-Za-z_]+", body)}
        forbidden = self._forbidden & tokens
        if forbidden:
            self._reject(
                f"sql_query: forbidden write/DDL keyword(s) in read-only mode: {sorted(forbidden)}"
            )

    @staticmethod
    def _strip_comments_and_strings(query: str) -> str:
        """Remove string literals and SQL comments so keyword scans see only structure."""
        no_block = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
        no_line = re.sub(r"--[^\n]*", " ", no_block)
        no_single = re.sub(r"'(?:''|[^'])*'", " ", no_line)
        return re.sub(r'"(?:""|[^"])*"', " ", no_single)
