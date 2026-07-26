"""LSP / contract tests for the shared ``HybridRetrieverBase`` (WS5 S4, PIR-701).

S4 introduces ``retrieval/hybrid_retriever_base.py`` defining
``HybridRetrieverBase(pirn.core.knot.Knot)`` as the shared house-interface base
for both concrete hybrid retrievers.  Its ``process`` is the NotImplementedError
contract; the two concrete subclasses (``HybridRetriever`` and
``HybridGraphRetriever``) fully override it.  These tests pin the
substitutability guarantee: both concretes are subclasses of the shared base,
the base's ``process`` raises with the concrete class name, and neither concrete
inherits the raising base ``process`` unchanged.

Imports of the moved modules are performed inside the test bodies (not at module
top) so this file always COLLECTS cleanly even before the parent's ``git mv``
moves land -- only the assertions fail until the refactor completes.  The suite
runs in the project's ``asyncio_mode = "auto"`` style, so ``async def test_*``
functions need no explicit marker.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def test_base_is_subclass_of_knot() -> None:
    """The shared base must extend the house ``Knot`` interface, not Protocol."""
    # Arrange
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act / Assert
    assert issubclass(HybridRetrieverBase, Knot)


def test_hybrid_retriever_is_subclass_of_base() -> None:
    """``HybridRetriever`` must be substitutable for the shared base."""
    # Arrange
    from pirn_agents.retrieval.hybrid_retriever import HybridRetriever
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act / Assert
    assert issubclass(HybridRetriever, HybridRetrieverBase)


def test_hybrid_graph_retriever_is_subclass_of_base() -> None:
    """``HybridGraphRetriever`` must be substitutable for the shared base."""
    # Arrange
    from pirn_agents.retrieval.graph_rag.hybrid_graph_retriever import (
        HybridGraphRetriever,
    )
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act / Assert
    assert issubclass(HybridGraphRetriever, HybridRetrieverBase)


async def test_base_process_raises_not_implemented_with_concrete_name() -> None:
    """A bare subclass's ``process`` must raise NotImplementedError naming it."""
    # Arrange
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    class _Bare(HybridRetrieverBase):
        pass

    bare = _Bare(_config=KnotConfig(id="bare"))

    # Act / Assert
    try:
        await bare.process()
    except NotImplementedError as exc:
        assert "_Bare must implement process()" in str(exc)
    else:  # pragma: no cover - the contract requires the raise above
        raise AssertionError("HybridRetrieverBase.process must raise NotImplementedError")


def test_hybrid_retriever_overrides_base_process() -> None:
    """``HybridRetriever`` must not inherit the raising base ``process``."""
    # Arrange
    from pirn_agents.retrieval.hybrid_retriever import HybridRetriever
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act / Assert
    assert HybridRetriever.process is not HybridRetrieverBase.process


def test_hybrid_graph_retriever_overrides_base_process() -> None:
    """``HybridGraphRetriever`` must not inherit the raising base ``process``."""
    # Arrange
    from pirn_agents.retrieval.graph_rag.hybrid_graph_retriever import (
        HybridGraphRetriever,
    )
    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act / Assert
    assert HybridGraphRetriever.process is not HybridRetrieverBase.process


def test_base_process_signature_returns_list_of_mappings() -> None:
    """Guard that the base declares the umbrella ``list[Mapping]`` return type."""
    # Arrange
    import inspect

    from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase

    # Act
    signature = inspect.signature(HybridRetrieverBase.process)

    # Assert -- the annotation resolves to list[Mapping[str, Any]] at authoring time.
    expected: Any = list[Mapping[str, Any]]
    assert signature.return_annotation in (expected, "list[Mapping[str, Any]]")
