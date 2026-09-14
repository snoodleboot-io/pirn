"""Unit tests for :class:`OilgasOptionalImport`."""

from __future__ import annotations

import sys
import types

import pytest

from pirn_oilgas.oilgas_optional_import import OilgasOptionalImport


class TestOilgasOptionalImport:
    def test_returns_the_imported_module(self) -> None:
        module = OilgasOptionalImport.require("json", "Caller: purpose")

        assert module is sys.modules["json"]

    def test_returns_a_module_already_in_sys_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = types.ModuleType("segyio")
        monkeypatch.setitem(sys.modules, "segyio", fake)

        assert OilgasOptionalImport.require("segyio", "Caller: purpose") is fake

    def test_missing_module_raises_install_hint_naming_the_distribution(self) -> None:
        with pytest.raises(ImportError) as excinfo:
            OilgasOptionalImport.require(
                "pirn_oilgas_absent_sdk.submodule", "SomeKnot: decoding bytes"
            )

        assert str(excinfo.value) == (
            "SomeKnot: decoding bytes requires pirn_oilgas_absent_sdk — install pirn-oilgas[oilgas]"
        )
        assert isinstance(excinfo.value.__cause__, ImportError)
