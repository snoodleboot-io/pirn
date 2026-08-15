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


class _Liar(str):
    """A ``str`` subclass whose ``split`` and ``__format__`` both lie.

    ``isinstance(x, str)`` admits subclasses, so every ``str`` method the class
    calls is really a call into attacker-controlled code. ``re`` is the exception:
    it reads the honest underlying buffer, which is why the validated *match text*
    — never the input object — is what may be quoted into a statement.
    """

    def __format__(self, format_spec: str) -> str:
        return 'x" ; DROP TABLE secrets; --'

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        return [self]


class _FormatOnlyLiar(str):
    """A ``str`` subclass overriding only ``__format__`` — the interpolation hook."""

    def __format__(self, format_spec: str) -> str:
        return 'x" ; DROP TABLE secrets; --'


class _SplitOnlyLiar(str):
    """A ``str`` subclass overriding only ``split`` — the part-decomposition hook."""

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        return ["users"]


class _StrOnlyLiar(str):
    """A ``str`` subclass overriding only ``__str__``, the usual normalisation hook."""

    def __str__(self) -> str:
        return 'x" ; DROP TABLE secrets; --'


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


class TestStrSubclassesCannotLieTheirWayIntoSql:
    """``isinstance(raw, str)`` admits subclasses, so ``str`` methods are hostile code.

    The class must derive the rendered identifier from the text it actually
    validated — the regex match against the honest buffer — rather than from any
    method or dunder the input object controls. These tests pin that no override
    of ``split``, ``__format__`` or ``__str__`` can change what is emitted.
    """

    def test_a_subclass_lying_in_split_and_format_still_renders_its_real_buffer(self) -> None:
        assert SqlIdentifier(_Liar("users")).sql == '"users"'

    def test_a_format_only_liar_cannot_inject(self) -> None:
        assert SqlIdentifier(_FormatOnlyLiar("users")).sql == '"users"'

    def test_a_split_only_liar_cannot_inject(self) -> None:
        assert SqlIdentifier(_SplitOnlyLiar("users")).sql == '"users"'

    def test_a_str_only_liar_cannot_inject(self) -> None:
        assert SqlIdentifier(_StrOnlyLiar("users")).sql == '"users"'

    def test_a_hostile_buffer_is_rejected_even_when_split_vouches_for_it(self) -> None:
        # split() claims a single clean part; the real buffer is an injection.
        # Validation must read the buffer, so this is refused at construction.
        with pytest.raises(ValueError, match="SqlIdentifier"):
            SqlIdentifier(_SplitOnlyLiar('users"; DROP TABLE secrets; --'))

    @pytest.mark.parametrize("liar", [_Liar, _FormatOnlyLiar, _SplitOnlyLiar, _StrOnlyLiar])
    def test_no_payload_survives_into_the_rendered_sql(self, liar: type[str]) -> None:
        rendered = SqlIdentifier(liar("users")).sql
        assert "DROP TABLE" not in rendered
        assert rendered.count('"') == 2

    def test_the_rendered_sql_is_a_plain_str_not_the_subclass(self) -> None:
        # A subclass leaking out would re-arm the same trick at the next
        # interpolation site downstream.
        assert type(SqlIdentifier(_Liar("users")).sql) is str

    def test_text_is_the_validated_plain_str_not_the_original_object(self) -> None:
        text = SqlIdentifier(_Liar("users")).text
        assert text == "users"
        assert type(text) is str


class TestQuotingIsClosedUnderRerendering:
    def test_rendered_sql_never_contains_an_unescaped_quote_run(self) -> None:
        # Every accepted identifier renders as an even number of double quotes
        # with no interior quote, so no input can terminate the quoted region.
        for raw in ("users", "public.users", "_x", "A1"):
            rendered = SqlIdentifier(raw).sql
            assert rendered.count('"') % 2 == 0
            assert '""' not in rendered
