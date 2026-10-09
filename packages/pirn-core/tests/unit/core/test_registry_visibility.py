"""Tests for :class:`RegistryVisibility`.

The mechanism that keeps an optional dependency from silently removing a knot
module from YAML name resolution. It lived as a private class copied verbatim
into all seven distributions' ``__init__`` and had **no test in any of them**;
consolidating it into core (PIR-873) is what makes one possible.
"""

from __future__ import annotations

import logging
import warnings

import pytest
from sweet_tea.sweet_tea_warning import SweetTeaWarning

from pirn.core.registry_visibility import RegistryVisibility


def _record(message: str, category: type[Warning] = SweetTeaWarning) -> warnings.WarningMessage:
    """Build the kind of record ``warnings.catch_warnings(record=True)`` collects."""
    return warnings.WarningMessage(
        message=category(message), category=category, filename="x.py", lineno=1
    )


def _skip_of(module: str) -> warnings.WarningMessage:
    return _record(f"Skipping module {module} due to missing optional dependency")


class TestLogSkips:
    def test_logs_one_warning_naming_the_module_the_cause_and_the_hint(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips(
                [_skip_of("my_pkg.backends.no_such_backend")],
                package="my_pkg",
                extra_hint="install my_pkg[all]",
            )

        (line,) = [r.getMessage() for r in caplog.records]
        assert "my_pkg.backends.no_such_backend" in line
        assert "install my_pkg[all]" in line
        # The cause comes from retrying the import, which fails for real here.
        assert "no_such_backend" in line

    def test_logs_one_line_per_skipped_module(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips(
                [_skip_of("my_pkg.a_missing"), _skip_of("my_pkg.b_missing")],
                package="my_pkg",
                extra_hint="hint",
            )

        assert len(caplog.records) == 2

    def test_a_module_that_imports_on_the_retry_reports_no_cause(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The warning is still surfaced; only the cause is unavailable.

        sweet_tea's message names the module but not why, so the cause is
        recovered by retrying the import. A module that imports fine on the
        retry leaves it unknown rather than inventing one — and the skip is
        still reported, because something did drop out of name resolution.
        """
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips(
                [_skip_of("pirn.core.registry_visibility")],
                package="my_pkg",
                extra_hint="hint",
            )

        (line,) = [r.getMessage() for r in caplog.records]
        assert "unknown import error" in line

    def test_ignores_a_warning_that_is_not_a_sweet_tea_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips(
                [_record("Skipping module x due to missing optional dependency", UserWarning)],
                package="my_pkg",
                extra_hint="hint",
            )

        assert caplog.records == []

    def test_ignores_a_sweet_tea_warning_that_is_not_a_skip(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Only the skip message is matched, so an unrelated warning is left alone."""
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips(
                [_record("some other sweet_tea concern")],
                package="my_pkg",
                extra_hint="hint",
            )

        assert caplog.records == []

    def test_no_records_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="my_pkg"):
            RegistryVisibility.log_skips([], package="my_pkg", extra_hint="hint")

        assert caplog.records == []

    def test_the_logger_is_the_importing_package(self, caplog: pytest.LogCaptureFixture) -> None:
        """Each distribution's skips reach a logger an operator can configure by name."""
        with caplog.at_level(logging.WARNING, logger="pirn_signal"):
            RegistryVisibility.log_skips(
                [_skip_of("pirn_signal.wavelets.missing")],
                package="pirn_signal",
                extra_hint="hint",
            )

        (record,) = caplog.records
        assert record.name == "pirn_signal"
