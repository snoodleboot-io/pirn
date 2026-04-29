"""YAML pipeline loader.

Strict by default: every node has a known type, every field is validated.
Loose mode (opt-in via ``allow_callable_refs=True``) permits dotted-path
imports of arbitrary Python callables.
"""
