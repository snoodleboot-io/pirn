"""Battery tests for :class:`ReadOnlySqlGuard` (PIR-812).

The guard is a conservative syntactic check, so its value is entirely in what it
refuses. These tests pin that surface as a battery rather than a handful of
examples: every statement previously confirmed to be rejected stays rejected, the
``SELECT ... INTO`` bypass is closed, and the reads that must keep working keep
working.

``SELECT ... INTO`` mattered because it is *table-creating DDL on Postgres* while
being a syntax error on SQLite — the first token is ``SELECT`` and no forbidden
keyword appears, so ``read_only=True`` could create a table.
"""

from __future__ import annotations

import pytest

from pirn_agents.tools.sql._read_only_sql_guard import ReadOnlySqlGuard


class TestSelectIntoIsRejected:
    """Regression (PIR-812): ``SELECT ... INTO`` is DDL, not a read."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * INTO newtbl FROM t",
            "select * into newtbl from t",
            "SELECT a, b INTO other FROM t",
            "SELECT * INTO TEMP tmptbl FROM t",
            "SELECT * INTO TEMPORARY tmptbl FROM t",
            "SELECT * INTO UNLOGGED newtbl FROM t",
            "  SELECT * INTO newtbl FROM t  ",
            "SELECT * /* c */ INTO newtbl FROM t",
            "SELECT *\n  INTO newtbl\n  FROM t",
            # MySQL's file-writing forms are the same shape.
            "SELECT * INTO OUTFILE '/tmp/x' FROM t",
            "SELECT * INTO DUMPFILE '/tmp/x' FROM t",
            # Smuggled through a CTE, which passes the first-token check as WITH.
            "WITH c AS (SELECT 1 AS n) SELECT * INTO newtbl FROM c",
            "WITH c AS (SELECT * INTO newtbl FROM t) SELECT * FROM c",
        ],
    )
    def test_rejects_select_into(self, query: str) -> None:
        with pytest.raises(ValueError, match="INTO"):
            ReadOnlySqlGuard().assert_read_only(query)


class TestPreviouslyRejectedStatementsStayRejected:
    """The confirmed-rejected battery: closing the INTO hole must not reopen these."""

    @pytest.mark.parametrize(
        "query",
        [
            "PRAGMA table_info(t)",
            "pragma foreign_keys = ON",
            "VACUUM",
            "ATTACH DATABASE 'x.db' AS y",
            "DETACH DATABASE y",
            "REPLACE INTO t VALUES (1)",
            "INSERT OR REPLACE INTO t VALUES (1)",
            "INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING",
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET x = 1",
            "DELETE FROM t",
            "TRUNCATE TABLE t",
            "REINDEX t",
            "ANALYZE t",
            "CREATE TABLE t (x int)",
            "DROP TABLE t",
            "ALTER TABLE t ADD COLUMN y int",
            "GRANT SELECT ON t TO bob",
            "REVOKE SELECT ON t FROM bob",
            "MERGE INTO t USING s ON t.id = s.id",
            "   DROP TABLE t",
            "dRoP TaBlE t",
            "(SELECT 1)",
            "SELECT 1; DROP TABLE t",
            "WITH x AS (SELECT 1) DELETE FROM t",
            "WITH x AS (INSERT INTO t VALUES (1) RETURNING *) SELECT * FROM x",
            "SELECT * FROM t FOR UPDATE",
            "",
            "   ",
            "-- just a comment",
        ],
    )
    def test_stays_rejected(self, query: str) -> None:
        with pytest.raises(ValueError):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize("query", ["VACUUM INTO 'copy.db'", "vacuum into 'copy.db'"])
    def test_vacuum_into_is_still_rejected_on_its_first_token(self, query: str) -> None:
        # ``VACUUM INTO`` was already rejected because its first token is not
        # SELECT/WITH — a stronger reason than the keyword scan, since it fires
        # before the statement body is inspected at all. Adding the INTO rule must
        # not shift it onto the weaker path.
        with pytest.raises(ValueError, match="only SELECT/WITH"):
            ReadOnlySqlGuard().assert_read_only(query)


class TestReadsStayAllowed:
    """The INTO rule must not cost the guard any legitimate read."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT id FROM t",
            "   SELECT 1",
            "SeLeCt 1",
            "WITH c AS (SELECT 1) SELECT * FROM c",
            "SELECT id FROM t WHERE id IN (SELECT id FROM u)",
            "SELECT * FROM t WHERE label = 'delete from x'",
            "SELECT * FROM t WHERE note = 'select * into other from t'",
            "SELECT id FROM t -- into is only mentioned here\n",
            "SELECT /* into */ id FROM t",
            "SELECT id FROM t WHERE n LIKE '%into%'",
            "SELECT id FROM t ORDER BY id LIMIT 10",
            "SELECT id FROM t;",
        ],
    )
    def test_allows_read(self, query: str) -> None:
        ReadOnlySqlGuard().assert_read_only(query)

    def test_allows_a_quoted_column_named_into(self) -> None:
        # ``INTO`` is a reserved word, so a column named ``into`` can only appear
        # quoted — and quoted identifiers are stripped before the keyword scan, on
        # the same path that already lets a column named ``delete`` through.
        ReadOnlySqlGuard().assert_read_only('SELECT "into" FROM t')
        ReadOnlySqlGuard().assert_read_only('SELECT t."into" AS n FROM t')


class TestCommentMarkersInsideLiteralsCannotHideStatements:
    """Regression (PIR-818): a ``/*`` in a literal must not open a real comment.

    The pre-scanner cleaner ran four sequential regexes and stripped block
    comments *before* string literals, so a ``/*`` inside one literal paired with
    a ``*/`` inside a later literal and deleted everything between them — the
    forbidden keyword *and* both semicolons — defeating the multi-statement check
    and the keyword scan at once.
    """

    @pytest.mark.parametrize(
        "query",
        [
            # The canonical defect: both semicolons and the DROP are deleted.
            "SELECT '/*' AS a; DROP TABLE t; SELECT '*/' AS b",
            "SELECT '/*' AS a; DELETE FROM t; SELECT '*/' AS b",
            "SELECT '/*' AS a; SELECT * INTO evil FROM t; SELECT '*/' AS b",
            # The same trick through quoted identifiers rather than literals.
            'SELECT "/*" AS a; DROP TABLE t; SELECT "*/" AS b',
            "SELECT `/*` AS a; DROP TABLE t; SELECT `*/` AS b",
            # A ``--`` inside a literal must not comment out the rest of the line.
            "SELECT '--' AS a; DROP TABLE t",
            "SELECT '--' AS a; SELECT * INTO evil FROM t",
            # Doubled quotes keep the scanner inside the literal, so the closing
            # quote is the real one and the DROP stays visible.
            "SELECT 'it''s /*' AS a; DROP TABLE t; SELECT '*/' AS b",
        ],
    )
    def test_comment_marker_in_literal_does_not_hide_a_write(self, query: str) -> None:
        with pytest.raises(ValueError):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT 'unterminated",
            "SELECT * FROM t WHERE x = 'a''",
            'SELECT "unterminated FROM t',
            "SELECT 1 /* unterminated",
            "SELECT `unterminated FROM t",
        ],
    )
    def test_unterminated_literal_or_block_comment_is_rejected(self, query: str) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            # MySQL only starts a line comment when ``--`` is followed by
            # whitespace, so ``1--1;`` is ``1 - -1`` and then a *second statement*.
            "SELECT 1--1; DROP TABLE t",
            "SELECT 1--1; SELECT * INTO evil FROM t",
            # MySQL executes the body of a ``/*! ... */`` version comment.
            "SELECT 1 /*! ; DROP TABLE t */",
            "SELECT 1 /*!32302 ; DROP TABLE t */",
        ],
    )
    def test_mysql_only_comment_forms_are_treated_as_code(self, query: str) -> None:
        with pytest.raises(ValueError):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            # Bracket and backtick identifiers are stripped like any other quote.
            "SELECT `into` FROM t",
            "SELECT [into] FROM t",
            "SELECT [delete] FROM `t`",
            'SELECT "a""b" FROM t',
            "SELECT 'it''s fine' AS a FROM t",
            "SELECT `a``b` FROM t",
            "SELECT [a]]b] FROM t",
            # Comment markers *inside* literals are still just text.
            "SELECT '/* not a comment */' AS a FROM t",
            "SELECT '-- not a comment' AS a FROM t",
            # A real block comment between two literals still gets stripped.
            "SELECT 'a' /* c */, 'b' FROM t",
            # ``*`` immediately followed by a block comment is multiplication.
            "SELECT 4*/*c*/2 AS n",
        ],
    )
    def test_reads_with_awkward_quoting_stay_allowed(self, query: str) -> None:
        ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query", ["-- c\nINSERT INTO t VALUES (1)", "/*c*/ INSERT INTO t VALUES (1)"]
    )
    def test_a_leading_comment_still_exposes_the_first_real_token(self, query: str) -> None:
        # Comment stripping runs before the first-token check, so the ``INSERT``
        # is seen and rejected on the strong first-token path. The scanner must
        # not change that.
        with pytest.raises(ValueError, match="only SELECT/WITH"):
            ReadOnlySqlGuard().assert_read_only(query)


class TestOtherQuotingFormsCannotHideStatements:
    """Two more ways to pair a quote across a write, found by attacking the scanner.

    Both are the *same shape* as the block-comment defect — one quoting form the
    scanner did not know about lets a quote character that the database treats as
    ordinary text be misread as opening a literal, so the literal swallows the
    statement separator and the write with it.
    """

    @pytest.mark.parametrize(
        "query",
        [
            # Postgres dollar-quoting: the ``'`` between the ``$$`` markers is
            # *text* to Postgres, but a scanner that does not know ``$$`` reads it
            # as opening a literal that runs to the ``'`` past the DROP.
            "SELECT $$ ' $$ ; DROP TABLE t; SELECT ' ",
            "SELECT $tag$ ' $tag$ ; DROP TABLE t; SELECT ' ",
            "SELECT $$ ' $$ ; SELECT * INTO evil FROM t; SELECT ' ",
        ],
    )
    def test_dollar_quoting_does_not_hide_a_write(self, query: str) -> None:
        with pytest.raises(ValueError):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            # Postgres ends a ``--`` comment at CR as well as LF, so everything
            # after the CR is live code.
            "SELECT 1 -- x\r; DROP TABLE t",
            "SELECT 1 -- \r DROP TABLE t",
            "SELECT 1 -- x\r; SELECT * INTO evil FROM t",
        ],
    )
    def test_carriage_return_ends_a_line_comment(self, query: str) -> None:
        with pytest.raises(ValueError):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize("query", ["SELECT $$ unterminated", "SELECT $tag$ unterminated"])
    def test_unterminated_dollar_quote_is_rejected(self, query: str) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            ReadOnlySqlGuard().assert_read_only(query)

    @pytest.mark.parametrize(
        "query",
        [
            # A dollar-quoted body is a string literal, so a keyword inside it is
            # no more dangerous than one inside ``'...'``.
            "SELECT $$abc$$ AS a",
            "SELECT $$ DROP TABLE t $$ AS a",
            "SELECT $tag$ delete from x $tag$ AS a",
            # ``$1`` is a positional parameter, not a dollar quote.
            "SELECT * FROM t WHERE id = $1",
            "SELECT * FROM t WHERE id = $1 AND n = $2",
        ],
    )
    def test_dollar_forms_that_must_stay_allowed(self, query: str) -> None:
        ReadOnlySqlGuard().assert_read_only(query)
