"""Tests for :class:`SqlIdentifier`, the validated SQL identifier value object.

A bound-table facade has to interpolate a table name into SQL — no dialect binds
an identifier as a parameter. :class:`SqlIdentifier` is the single place that
decision lives, so these tests are the security tests for the whole facade: they
pin the accepted character set, the dotted-part limit, and a battery of hostile
inputs that must be rejected at construction rather than reaching a database.
"""

from __future__ import annotations

import pytest

from pirn_agents.connectors.sql_identifier import SqlIdentifier


class TestAcceptedIdentifiers:
    def test_bare_name_is_quoted(self) -> None:
        assert SqlIdentifier("users").sql == '"users"'

    def test_schema_qualified_name_quotes_each_part(self) -> None:
        assert SqlIdentifier("public.users").sql == '"public"."users"'

    @pytest.mark.parametrize("raw", ["users", "_private", "Users2", "a", "T_1_x"])
    def test_portable_names_are_accepted(self, raw: str) -> None:
        assert SqlIdentifier(raw).sql == f'"{raw}"'

    def test_case_is_preserved_exactly(self) -> None:
        # Quoting makes identifiers case-sensitive in both SQLite and Postgres,
        # so the facade must never fold case behind the caller's back.
        assert SqlIdentifier("MixedCase").sql == '"MixedCase"'

    def test_text_exposes_the_unquoted_original(self) -> None:
        assert SqlIdentifier("public.users").text == "public.users"


class TestHostileIdentifiersAreRejected:
    @pytest.mark.parametrize(
        "raw",
        [
            "users; DROP TABLE users",
            'users"; DROP TABLE users; --',
            'users" --',
            '"users"',
            '"',
            "users--",
            "users/*comment*/",
            "/*x*/users",
            "users'",
            "'users'",
            "`users`",
            "[users]",
            "users%",
            "users)",
            "(SELECT 1)",
            "users UNION SELECT",
            "us ers",
            "users\ttab",
            "users\nDROP",
            "users\x00",
            "users\\",
            "1users",
            "9",
            "",
            "   ",
            ".",
            ".users",
            "users.",
            "a..b",
            "a.b.c",
            "usérs",
            "таблица",
            "users​",
        ],
    )
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValueError, match="SqlIdentifier"):
            SqlIdentifier(raw)

    def test_non_string_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="SqlIdentifier"):
            SqlIdentifier(object())  # pyright: ignore[reportArgumentType]

    def test_rejection_message_does_not_echo_the_payload(self) -> None:
        # The raw value can be attacker-controlled and lands in logs; the error
        # names the offending part's position, never replays the payload.
        with pytest.raises(ValueError) as info:
            SqlIdentifier("users; DROP TABLE secrets")
        assert "DROP TABLE secrets" not in str(info.value)


class TestQuotingIsClosedUnderRerendering:
    def test_rendered_sql_never_contains_an_unescaped_quote_run(self) -> None:
        # Every accepted identifier renders as an even number of double quotes
        # with no interior quote, so no input can terminate the quoted region.
        for raw in ("users", "public.users", "_x", "A1"):
            rendered = SqlIdentifier(raw).sql
            assert rendered.count('"') % 2 == 0
            assert '""' not in rendered
