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
