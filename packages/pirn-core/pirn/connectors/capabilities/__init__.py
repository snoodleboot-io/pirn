"""Capability interfaces for connectors.

Each concrete connector subclass declares which of these mixins it
satisfies — knots compose against the capability, not the concrete
vendor class. ``ApiClient.request`` is the generic escape hatch for an
operation neither covers; prefer vendor-typed methods + capability
inheritance.
"""
