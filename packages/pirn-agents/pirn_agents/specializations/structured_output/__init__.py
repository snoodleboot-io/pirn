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
