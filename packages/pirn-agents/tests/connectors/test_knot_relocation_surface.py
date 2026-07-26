"""Characterization tests pinning the relocated knot import surface (PIR-699).

WS5 S2 moves five vending ``Knot`` classes out of the flat ``pirn_agents``
root into domain ``knots/`` subpackages. These tests pin two invariants:

1. Each knot resolves at its NEW canonical module path and is a ``Knot``.
2. Each OLD flat-root module path no longer resolves (``ModuleNotFoundError``).
"""

from __future__ import annotations

import importlib

import pytest
from pirn.core.knot import Knot

NEW_KNOT_PATHS: tuple[tuple[str, str], ...] = (
    ("pirn_agents.connectors.knots.http_connector_knot", "HttpConnectorKnot"),
    ("pirn_agents.connectors.knots.search_connector_knot", "SearchConnectorKnot"),
    ("pirn_agents.connectors.knots.sql_connector_knot", "SqlConnectorKnot"),
    ("pirn_agents.llm.knots.llm_provider_knot", "LLMProviderKnot"),
    ("pirn_agents.tools.knots.tool_client_knot", "ToolClientKnot"),
)

OLD_ROOT_MODULES: tuple[str, ...] = (
    "pirn_agents.http_connector_knot",
    "pirn_agents.search_connector_knot",
    "pirn_agents.sql_connector_knot",
    "pirn_agents.llm_provider_knot",
    "pirn_agents.tool_client_knot",
)


@pytest.mark.parametrize(("module_path", "class_name"), NEW_KNOT_PATHS)
def test_relocated_knot_resolves_at_new_path(module_path: str, class_name: str) -> None:
    # Arrange / Act
    module = importlib.import_module(module_path)
    knot_class = getattr(module, class_name)

    # Assert
    assert isinstance(knot_class, type)
    assert issubclass(knot_class, Knot)


@pytest.mark.parametrize("old_module_path", OLD_ROOT_MODULES)
def test_old_root_knot_path_no_longer_resolves(old_module_path: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(old_module_path)
