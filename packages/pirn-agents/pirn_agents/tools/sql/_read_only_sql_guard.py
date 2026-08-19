"""Read-only SQL statement guard for the ``sql_query`` tool.

:class:`ReadOnlySqlGuard` performs a conservative, dependency-free check that a
statement is a single read (``SELECT``/``WITH``) and contains no DML/DDL
keyword. String literals and comments are stripped before scanning so a keyword
inside a quoted value does not trigger a false positive. The forbidden-keyword
set is built once in the constructor rather than on every call.

**Why a scanner and not regexes.** The stripping is a single left-to-right state
machine (:meth:`ReadOnlySqlGuard._strip_comments_and_strings`). It used to be
four sequential regex passes that removed block comments *before* string
literals, so a ``/*`` inside one literal opened a comment that ran to a ``*/``
inside a later literal and deleted everything between them::

    SELECT '/*' AS a; DROP TABLE t; SELECT '*/' AS b   ->   SELECT   AS b

That deleted the ``DROP`` *and* both semicolons, defeating the multi-statement
check and the keyword scan at the same time (PIR-818). Whether a character opens
a comment depends on whether the scan is already inside a literal, which is
state no ordering of independent regex passes can express.

**Scope of protection.** This is a best-effort syntactic guard, *not* a SQL
parser and *not* a substitute for a least-privilege, read-only database role.
For untrusted input, also connect with a database account that lacks write
permission. See ``pirn_agents/TOOLS.md``.
"""

from __future__ import annotations

import re

from pirn.security.security_guard import SecurityGuard


class ReadOnlySqlGuard(SecurityGuard):
    """Reject any statement that is not a single read-only ``SELECT``/``WITH``."""

    def __init__(self) -> None:
        """Build the forbidden write/DDL keyword set and the quote table once."""
        self._quote_closers: dict[str, str] = {"'": "'", '"': '"', "`": "`", "[": "]"}
        self._dollar_tag: re.Pattern[str] = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
        self._line_end: re.Pattern[str] = re.compile(r"[\n\r]")
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

        ``INTO`` is checked separately from :attr:`_forbidden` because it is not
        itself a write keyword — it is a clause that turns an otherwise ordinary
        read into DDL. ``SELECT * INTO newtbl FROM t`` starts with ``SELECT`` and
        names no forbidden keyword, yet it *creates a table* on PostgreSQL (and
        ``SELECT ... INTO OUTFILE`` writes a file on MySQL), so it passed the
        guard and let ``read_only=True`` write (PIR-812). It is only a syntax
        error on SQLite, which is why the hole went unnoticed.

        The check runs after the first-token check, so a statement already
        rejected for not beginning with ``SELECT``/``WITH`` — ``INSERT INTO``,
        ``REPLACE INTO``, ``MERGE INTO``, ``VACUUM INTO`` — keeps being rejected
        for that stronger reason, before its body is inspected at all. Scanning
        the whole body rather than only the text after ``SELECT`` is deliberate:
        it also catches the form smuggled inside a ``WITH`` CTE.

        A column genuinely named ``into`` is unaffected: ``INTO`` is a reserved
        word, so such a column can only be written quoted, and quoted identifiers
        are stripped before the scan — the same path that already lets a column
        named ``delete`` through.

        Args:
            query: The SQL text to vet.

        Raises:
            ValueError: If ``query`` is empty, contains multiple statements, does
                not start with ``SELECT``/``WITH``, or contains a write/DDL
                keyword or ``INTO``.
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
        if "INTO" in tokens:
            self._reject(
                "sql_query: INTO is not allowed in read-only mode — 'SELECT ... INTO' "
                "creates a table on PostgreSQL, and writes a file on MySQL"
            )

    def _strip_comments_and_strings(self, query: str) -> str:
        """Remove string literals and SQL comments so keyword scans see only structure.

        A single left-to-right pass. At each position the scanner is in exactly
        one state — ordinary SQL, inside a quoted run, or inside a comment — and
        only the ordinary state can open a new quote or comment, which is why a
        ``/*`` inside a literal is inert (PIR-818). Every stripped run is replaced
        by a space so it cannot fuse the tokens on either side of it.

        Where dialects disagree about what counts as a comment, the scanner takes
        the reading that *strips the least*. Stripping less can only make the
        guard see more keywords and semicolons than the database will, which
        costs a false rejection; stripping more is what hides a write.

        - **Quoted runs.** ``'literal'``, ``"identifier"``, ```identifier``` and
          ``[identifier]`` all end at their closing character, which is escaped by
          doubling (``''``, ``""``, ``` `` ```, ``]]``). A backslash is *not* an
          escape even though MySQL treats it as one by default: reading ``'a\\'``
          as a finished literal (the standard, Postgres and SQLite reading)
          exposes any statement that follows it, while honouring the backslash
          would swallow that statement.
        - **Block comments do not nest**, per the SQL standard, MySQL and SQLite;
          the first ``*/`` closes. Postgres does nest them, but nesting strips
          more, so the non-nesting reading is the conservative one.
        - **Line comments** start at ``--`` only when it is followed by whitespace
          or end of input. That is MySQL's rule, and it is the strictest of the
          three: Postgres and SQLite also comment out anything MySQL does. Under
          the looser reading ``SELECT 1--1; DROP TABLE t`` is a clean read, but
          MySQL sees ``1 - -1`` and then a second statement. The cost is that
          ``-- drop`` written without the space is read as code and rejected.
        - **A line comment ends at CR as well as LF.** Postgres' lexer terminates
          ``--`` at ``[\\n\\r]``, so under an LF-only rule everything after a bare
          CR — ``SELECT 1 -- x\\r; DROP TABLE t`` — is live code the guard never
          sees.
        - **Dollar-quoted strings** (``$$...$$``, ``$tag$...$tag$``) are Postgres
          literals and are stripped as a unit. Skipping them is not merely
          incomplete, it is exploitable: a ``'`` *inside* the dollar-quoted body is
          ordinary text to Postgres, but a scanner ignorant of ``$$`` reads it as
          opening a literal that then runs past a statement separator and swallows
          the write with it. ``$1`` stays a positional parameter — a tag must be
          empty or start with a letter or underscore.
        - **MySQL version comments** (``/*!...*/``, ``/*!50000...*/``) are executed
          by MySQL, so their bodies are scanned as code rather than stripped.
        - ``#`` is deliberately *not* treated as a comment. MySQL alone honours it,
          and ignoring it only over-exposes text.

        An unterminated quoted run, dollar quote or block comment is rejected
        rather than stripped to end of input: it is not a well-formed statement in
        any dialect, and silently discarding the tail is exactly the failure this
        method exists to prevent. A line comment closed by end of input is
        ordinary and is not an error.

        Args:
            query: The raw SQL text.

        Returns:
            ``query`` with every literal, identifier quote and comment replaced by
            a single space.

        Raises:
            ValueError: If a quoted run, dollar quote or block comment is never
                closed.
        """
        cleaned: list[str] = []
        index = 0
        length = len(query)
        version_comment_depth = 0
        while index < length:
            char = query[index]
            closer = self._quote_closers.get(char)
            if closer is not None:
                index = self._skip_quoted_run(query, index, closer)
                cleaned.append(" ")
                continue
            if query.startswith("/*!", index):
                version_comment_depth += 1
                cleaned.append(" ")
                index += 3
                continue
            if query.startswith("/*", index):
                close_at = query.find("*/", index + 2)
                if close_at < 0:
                    self._reject("sql_query: unterminated block comment in read-only mode")
                cleaned.append(" ")
                index = close_at + 2
                continue
            if version_comment_depth > 0 and query.startswith("*/", index):
                version_comment_depth -= 1
                cleaned.append(" ")
                index += 2
                continue
            if self._starts_line_comment(query, index):
                line_end = self._line_end.search(query, index)
                cleaned.append(" ")
                index = length if line_end is None else line_end.start()
                continue
            if char == "$":
                opener = self._dollar_tag.match(query, index)
                if opener is not None:
                    tag = opener.group()
                    close_at = query.find(tag, opener.end())
                    if close_at < 0:
                        self._reject(
                            f"sql_query: unterminated dollar-quoted string {tag!r} at "
                            f"position {index} in read-only mode"
                        )
                    cleaned.append(" ")
                    index = close_at + len(tag)
                    continue
            cleaned.append(char)
            index += 1
        return "".join(cleaned)

    def _skip_quoted_run(self, query: str, start: int, closer: str) -> int:
        """Return the index just past the quoted run opening at ``start``.

        Args:
            query: The raw SQL text.
            start: Index of the opening quote character.
            closer: The character that closes this run; doubling it escapes it.

        Returns:
            The index of the first character after the closing quote.

        Raises:
            ValueError: If the run is never closed.
        """
        index = start + 1
        doubled = closer * 2
        while True:
            close_at = query.find(closer, index)
            if close_at < 0:
                self._reject(
                    f"sql_query: unterminated quoted text starting at position {start} "
                    "in read-only mode"
                )
            if query.startswith(doubled, close_at):
                index = close_at + 2
                continue
            return close_at + 1

    @staticmethod
    def _starts_line_comment(query: str, index: int) -> bool:
        """Report whether a ``--`` line comment starts at ``index``.

        Requires whitespace or end of input after the ``--``, which is MySQL's
        rule and the strictest of the supported dialects'.

        Args:
            query: The raw SQL text.
            index: The position to test.

        Returns:
            ``True`` if a line comment starts here.
        """
        if not query.startswith("--", index):
            return False
        after = index + 2
        return after >= len(query) or query[after].isspace()
