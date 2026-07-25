"""``RouterRagPipeline`` — classify the query, retrieve from the chosen index.

A :class:`SubTapestry` that wires:

1. :class:`QueryRouteClassifier` — pick the best route for the query.
2. :class:`RoutedRetriever` — retrieve from the store bound to that route in the
   :class:`RouteTable`.
3. :class:`RAGSynthesizer` — synthesize a grounded answer over the hits.

Routing lets one agent front several specialised indexes (e.g. docs vs. code vs.
tickets) and send each query only to the index most likely to answer it.

References:
    - Jeong et al., "Adaptive-RAG" (2024): https://arxiv.org/abs/2403.14403
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.rag.query_route_classifier import QueryRouteClassifier
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.route_table import RouteTable
from pirn_agents.specializations.rag.routed_retriever import RoutedRetriever


class RouterRagPipeline(SubTapestry):
    """Route the query to one index in a :class:`RouteTable`, then synthesize."""

    def __init__(
        self,
        *,
        query: Knot | str,
        routes: Knot | RouteTable,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            routes=routes,
            llm=llm,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        routes: RouteTable,
        llm: LLMProvider,
        top_k: int = 5,
        **_: Any,
    ) -> Any:
        """Wire classification → routed retrieval → synthesis.

        Args:
            query: The user query to route and answer.
            routes: The table of candidate stores.
            llm: The provider used for classification and synthesis.
            top_k: Number of hits fed to synthesis.

        Returns:
            The :class:`RAGSynthesizer` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query``/``routes``/``llm`` are the wrong type.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"RouterRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(routes, RouteTable):
            raise TypeError(
                f"RouterRagPipeline: routes must be a RouteTable, got {type(routes).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"RouterRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        route = QueryRouteClassifier(
            query=query,
            llm=llm,
            route_names=routes.route_names(),
            _config=KnotConfig(id="classify"),
        )
        documents = RoutedRetriever(
            route=route,
            routes=routes,
            query=query,
            top_k=top_k,
            _config=KnotConfig(id="route"),
        )
        return RAGSynthesizer(
            query=query,
            documents=documents,
            llm=llm,
            _config=KnotConfig(id="synthesize"),
        )
