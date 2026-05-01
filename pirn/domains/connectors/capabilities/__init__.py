"""Capability interfaces for connectors.

Each concrete connector subclass declares which of these mixins it
satisfies — knots compose against the capability, not the concrete
vendor class. ``ApiClient.request`` remains as a deprecated escape
hatch; new code should prefer vendor-typed methods + capability
inheritance.
"""
