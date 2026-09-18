"""One implementation per SCD type, with the surface the deleted siblings had (PIR-873).

The audit found three Type 1 implementations, four Type 2 and three Type 7. The
duplicates are deleted; what made each distinguishable is now an input on the
surviving knot. These tests pin exactly that, on real SQLite pools:

* ``rows`` from an upstream knot, the only thing ``ScdType1MergeKnot`` /
  ``ScdType2MergeKnot`` / ``ScdType7MergeKnot`` did differently;
* ``row_hash_column`` change detection, the only thing ``DbtStyleSnapshot`` did
  differently — and the hash is ``ContentHasher``'s, not a ``"|"``-joined MD5,
  so a value containing the separator no longer aliases onto another row;
* ``current_columns`` mirroring, the only thing ``ScdType7Hybrid`` did
  differently;
* the summary keys the module docstrings promise. The knots returned
  ``inserted`` / ``updated`` / ``expired`` while their docstrings documented
  ``rows_inserted`` / ``rows_updated`` / ``rows_expired``; the documented names
  are now the real ones, so every assertion here on ``rows_*`` fails on the
  pre-PIR-873 tree.
"""

from __future__ import annotations

import unittest

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations.scd.scd_type_1 import ScdType1
from pirn_data.specializations.scd.scd_type_2 import ScdType2
from pirn_data.specializations.scd.scd_type_7 import ScdType7


class TestSummaryKeysMatchTheDocumentedNames(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE dim1 (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        await self.pool.execute(
            "CREATE TABLE dim2 ("
            "  id INTEGER NOT NULL, name TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL, valid_to TEXT, is_current INTEGER NOT NULL)"
        )
        await self.pool.execute(
            "CREATE TABLE dim7 ("
            "  scd_id INTEGER NOT NULL, id INTEGER NOT NULL, name TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL, valid_to TEXT, is_current INTEGER NOT NULL)"
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_type_1_reports_rows_inserted_and_rows_updated(self) -> None:
        knot = ScdType1(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim1",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd1"),
        )
        first = await knot.process(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim1",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert first == {
            "succeeded": True,
            "target_table": "dim1",
            "rows_inserted": 1,
            "rows_updated": 0,
        }
        second = await knot.process(
            rows=[(1, "alice-2")],
            target_pool=self.pool,
            target_table="dim1",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert second["rows_inserted"] == 0
        assert second["rows_updated"] == 1

    async def test_type_2_reports_rows_inserted_and_rows_expired(self) -> None:
        knot = ScdType2(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim2",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd2"),
        )
        first = await knot.process(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim2",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert first["rows_inserted"] == 1
        assert first["rows_expired"] == 0
        second = await knot.process(
            rows=[(1, "alice-2")],
            target_pool=self.pool,
            target_table="dim2",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert second["rows_inserted"] == 1
        assert second["rows_expired"] == 1

    async def test_type_7_reports_rows_inserted_and_rows_expired(self) -> None:
        knot = ScdType7(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd7"),
        )
        summary = await knot.process(
            rows=[(1, "alice")],
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert summary["rows_inserted"] == 1
        assert summary["rows_expired"] == 0
        rows = await self.pool.fetch_all("SELECT scd_id, id, name FROM dim7")
        assert rows == [(1, 1, "alice")]


class TestRowsInputReplacesTheDeletedMergeKnots(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE dim1 (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _knot(self) -> ScdType1:
        return ScdType1(
            rows=[],
            target_pool=self.pool,
            target_table="dim1",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd1"),
        )

    async def test_rows_from_upstream_are_merged(self) -> None:
        await self._knot().process(
            rows=[(1, "alice"), (2, "bob")],
            target_pool=self.pool,
            target_table="dim1",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert await self.pool.fetch_all("SELECT id, name FROM dim1 ORDER BY id") == [
            (1, "alice"),
            (2, "bob"),
        ]

    async def test_rows_and_source_query_together_are_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "not both"):
            await self._knot().process(
                rows=[(1, "alice")],
                source_pool=self.pool,
                source_query="SELECT id, name FROM dim1",
                target_pool=self.pool,
                target_table="dim1",
                primary_keys=("id",),
                column_names=("id", "name"),
            )

    async def test_neither_rows_nor_source_query_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "supply either rows or source_pool"):
            await self._knot().process(
                target_pool=self.pool,
                target_table="dim1",
                primary_keys=("id",),
                column_names=("id", "name"),
            )

    async def test_row_width_is_checked_in_both_modes(self) -> None:
        with self.assertRaisesRegex(ValueError, "row width 3 does not match"):
            await self._knot().process(
                rows=[(1, "alice", "extra")],
                target_pool=self.pool,
                target_table="dim1",
                primary_keys=("id",),
                column_names=("id", "name"),
            )


class TestRowHashModeReplacesDbtStyleSnapshot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute(
            "CREATE TABLE snap ("
            "  id INTEGER NOT NULL, part_a TEXT NOT NULL, part_b TEXT NOT NULL,"
            "  dbt_valid_from TEXT NOT NULL, dbt_valid_to TEXT,"
            "  dbt_is_current INTEGER NOT NULL, dbt_scd_id TEXT NOT NULL)"
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def _run(self, rows: list[tuple[object, ...]]) -> dict[str, object]:
        knot = ScdType2(
            rows=rows,
            target_pool=self.pool,
            target_table="snap",
            primary_keys=("id",),
            column_names=("id", "part_a", "part_b"),
            effective_date_column="dbt_valid_from",
            expiry_date_column="dbt_valid_to",
            current_flag_column="dbt_is_current",
            row_hash_column="dbt_scd_id",
            _config=KnotConfig(id="snap"),
        )
        return await knot.process(
            rows=rows,
            target_pool=self.pool,
            target_table="snap",
            primary_keys=("id",),
            column_names=("id", "part_a", "part_b"),
            effective_date_column="dbt_valid_from",
            expiry_date_column="dbt_valid_to",
            current_flag_column="dbt_is_current",
            row_hash_column="dbt_scd_id",
        )

    async def test_unchanged_row_is_skipped_by_hash(self) -> None:
        assert (await self._run([(1, "a", "b")]))["rows_inserted"] == 1
        second = await self._run([(1, "a", "b")])
        assert second["rows_inserted"] == 0
        assert second["rows_expired"] == 0

    async def test_separator_bearing_change_is_detected(self) -> None:
        """``("a|b", "c")`` -> ``("a", "b|c")`` is a real change, not a hash collision.

        ``md5("|".join(str(v) for v in values))`` maps both to ``"a|b|c"``, so
        the pre-PIR-873 ``DbtStyleSnapshot`` saw no change and never versioned
        the row. ``ContentHasher`` canonicalises the tuple, so the hashes differ.
        """
        assert (await self._run([(1, "a|b", "c")]))["rows_inserted"] == 1
        second = await self._run([(1, "a", "b|c")])
        assert second["rows_inserted"] == 1
        assert second["rows_expired"] == 1
        stored = await self.pool.fetch_all(
            "SELECT part_a, part_b, dbt_is_current FROM snap ORDER BY dbt_is_current"
        )
        assert stored == [("a|b", "c", 0), ("a", "b|c", 1)]

    async def test_hash_column_may_not_appear_in_column_names(self) -> None:
        knot = ScdType2(
            rows=[],
            target_pool=self.pool,
            target_table="snap",
            primary_keys=("id",),
            column_names=("id", "part_a"),
            _config=KnotConfig(id="snap"),
        )
        with self.assertRaisesRegex(ValueError, "must not appear in column_names"):
            await knot.process(
                rows=[],
                target_pool=self.pool,
                target_table="snap",
                primary_keys=("id",),
                column_names=("id", "part_a"),
                row_hash_column="part_a",
            )


class TestCurrentColumnsReplaceScdType7Hybrid(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute(
            "CREATE TABLE dim7 ("
            "  scd_id INTEGER NOT NULL, id INTEGER NOT NULL, tier TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL, valid_to TEXT, is_current INTEGER NOT NULL,"
            "  current_tier TEXT NOT NULL)"
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def _run(self, rows: list[tuple[object, ...]]) -> dict[str, object]:
        knot = ScdType7(
            rows=rows,
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "tier"),
            current_columns={"tier": "current_tier"},
            _config=KnotConfig(id="scd7"),
        )
        return await knot.process(
            rows=rows,
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "tier"),
            current_columns={"tier": "current_tier"},
        )

    async def test_mirror_is_backfilled_across_history(self) -> None:
        await self._run([(1, "gold")])
        await self._run([(1, "platinum")])
        rows = await self.pool.fetch_all(
            "SELECT scd_id, tier, current_tier, is_current FROM dim7 ORDER BY scd_id"
        )
        assert rows == [(1, "gold", "platinum", 0), (2, "platinum", "platinum", 1)]

    async def test_mirror_mapping_must_cover_every_non_key_column(self) -> None:
        knot = ScdType7(
            rows=[],
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "tier"),
            current_columns={},
            _config=KnotConfig(id="scd7"),
        )
        with self.assertRaisesRegex(ValueError, "current_columns missing entries"):
            await knot.process(
                rows=[],
                target_pool=self.pool,
                target_table="dim7",
                primary_keys=("id",),
                column_names=("id", "tier"),
                current_columns={},
            )
