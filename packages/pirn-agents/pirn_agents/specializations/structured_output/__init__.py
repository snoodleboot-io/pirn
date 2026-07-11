"""Structured-output agent specializations.

This package contains :class:`SubTapestry` shapes that coerce LLM
output into structured forms — JSON dicts, pydantic models, fixed
enum labels, and YAML — with self-correcting retry loops on parse
or validation failure.

It also hosts the F20 native, single-pass structured-output paths —
capability-gated native schema mapping, forced tool-choice extraction, and
grammar/regex-constrained decoding — behind one unified
:class:`StructuredDecoder` / :func:`structured_decode` entry point that falls
back to the retry pipeline when no native path is available.
"""

from pirn_agents.specializations.structured_output.constrained_decoding_mapper import (
    ConstrainedDecodingMapper,
)
from pirn_agents.specializations.structured_output.forced_tool_choice_extractor import (
    ForcedToolChoiceExtractor,
)
from pirn_agents.specializations.structured_output.native_schema_mapper import (
    NativeSchemaMapper,
)
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)
from pirn_agents.specializations.structured_output.structured_decoder import (
    StructuredDecoder,
    structured_decode,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)

__all__: list[str] = [
    "ConstrainedDecodingMapper",
    "ForcedToolChoiceExtractor",
    "NativeSchemaMapper",
    "StructuredDecodeError",
    "StructuredDecoder",
    "StructuredOutputCapability",
    "StructuredOutputProvider",
    "structured_decode",
]
