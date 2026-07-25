"""Security primitives shared across the framework.

Credential holding, policy-guard base, and SSRF-vetted endpoints live in their
own concrete modules; this package does not re-export them (house convention
forbids import forwarding, enforced by ``scripts/check_no_import_forwarding.py``).
For example: ``from pirn.security.credential_ref import CredentialRef``.
"""
