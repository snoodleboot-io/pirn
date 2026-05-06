"""``SchemaEnforcer`` — validate AgentResponse content against a Pydantic model.

A :class:`Knot` that parses the JSON content of an :class:`AgentResponse`
and validates it against a caller-supplied :class:`pydantic.BaseModel`
subclass. Returns the parsed model instance on success or raises
:class:`pydantic.ValidationError` on failure.

Algorithm:
    1. Receive ``response`` (AgentResponse) and ``model_class`` (type[BaseModel]).
    2. Validate that ``response`` is an AgentResponse and ``model_class`` is a
       BaseModel subclass; raise ``TypeError`` on failure.
    3. Attempt to parse ``response.content`` as JSON; raise ``ValueError`` on
       ``JSONDecodeError``.
    4. Call ``model_class.model_validate(data)`` and return the model instance.


References:
    - Pydantic ``BaseModel.model_validate``:
      https://docs.pydantic.dev/latest/concepts/models/
    - :class:`pirn.domains.agents.types.agent_response.AgentResponse`
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class SchemaEnforcer(Knot):
    """Parse and validate AgentResponse JSON content against a BaseModel."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        model_class: Knot | type[BaseModel],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, model_class=model_class, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        model_class: type[BaseModel],
        **_: Any,
    ) -> BaseModel:
        """Parse the response content as JSON and validate against the model class.

        Args:
            response: The agent response whose content is validated.
            model_class: A BaseModel subclass to validate the parsed JSON against.

        Returns:
            A validated model instance produced by model_class.model_validate.

        Raises:
            TypeError: If response is not an AgentResponse or model_class is not a BaseModel subclass.
            ValueError: If response content is not valid JSON.
            ValidationError: If the parsed data does not satisfy the model schema.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                f"SchemaEnforcer: response must be an AgentResponse, got {type(response).__name__}"
            )
        if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
            raise TypeError(
                f"SchemaEnforcer: model_class must be a BaseModel subclass, got {model_class!r}"
            )
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"SchemaEnforcer: response content is not valid JSON: {exc}") from exc
        return model_class.model_validate(data)
