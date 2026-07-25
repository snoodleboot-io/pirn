"""Identity resolution.

Resolvers are defined in — and imported from — their own concrete modules; this
package does not re-export them (house convention forbids import forwarding,
enforced by ``scripts/check_no_import_forwarding.py``). For example:
``from pirn.core.identity.identity_resolver import IdentityResolver``.
"""
