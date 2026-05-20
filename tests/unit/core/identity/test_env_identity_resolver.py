from __future__ import annotations

import unittest
from unittest.mock import patch

from pirn.core.identity.env_identity_resolver import EnvIdentityResolver


class TestEnvIdentityResolver(unittest.TestCase):
    def test_returns_first_matching_var(self) -> None:
        with patch.dict("os.environ", {"GITHUB_ACTOR": "octocat"}, clear=False):
            result = EnvIdentityResolver().resolve()
        self.assertEqual(result, "octocat")

    def test_skips_empty_vars(self) -> None:
        env = {"GITHUB_ACTOR": "", "GITLAB_USER_LOGIN": "gl-user"}
        with patch.dict("os.environ", env, clear=False):
            result = EnvIdentityResolver().resolve()
        self.assertEqual(result, "gl-user")

    def test_returns_none_when_no_vars_set(self) -> None:
        keys = ["GITHUB_ACTOR", "GITLAB_USER_LOGIN", "CI_USER", "BUILD_USER"]
        clean_env = {k: "" for k in keys}
        with patch.dict("os.environ", clean_env, clear=False):
            result = EnvIdentityResolver().resolve()
        self.assertIsNone(result)

    def test_custom_var_list(self) -> None:
        with patch.dict("os.environ", {"MY_USER": "alice"}, clear=False):
            result = EnvIdentityResolver(vars=["MY_USER"]).resolve()
        self.assertEqual(result, "alice")

    def test_strips_whitespace(self) -> None:
        with patch.dict("os.environ", {"GITHUB_ACTOR": "  bob  "}, clear=False):
            result = EnvIdentityResolver().resolve()
        self.assertEqual(result, "bob")
