"""``KnotConfig.timeout`` and ``KnotConfig.retry`` (ADR agents-speaks-core, WS0).

Both are execution policy, not identity: they must never reach the config
dump ``knot_config_hash`` is computed from, or every existing recording
would stop replaying.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.core.content_hasher import ContentHasher
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy


class TestTimeoutAndRetryFields(unittest.TestCase):
    # Same golden hashes as ``test_knot_config.py`` -- computed on main
    # before either field existed.
    golden_minimal = "sha256:20d4f1367644ce1dcfb00c4d68a5595ad4cf695df734a50a4339e8c69937b62a"
    golden_full = "sha256:dffa07aaa0568ebac148c78c33e310dd58d960ed405bc50aaee655e999151ec0"

    def test_default_to_none(self) -> None:
        cfg = KnotConfig(id="k")
        self.assertIsNone(cfg.timeout)
        self.assertIsNone(cfg.retry)

    def test_store_the_values(self) -> None:
        policy = KnotRetryPolicy(max_attempts=3)
        cfg = KnotConfig(id="k", timeout=2.5, retry=policy)
        self.assertEqual(cfg.timeout, 2.5)
        self.assertIs(cfg.retry, policy)

    def test_timeout_must_be_positive(self) -> None:
        for bad in (0, -1.0):
            with self.subTest(timeout=bad), self.assertRaises(ValidationError):
                KnotConfig(id="k", timeout=bad)

    def test_retry_accepts_a_mapping_and_coerces_it(self) -> None:
        cfg = KnotConfig(id="k", retry={"max_attempts": 3})
        self.assertIsInstance(cfg.retry, KnotRetryPolicy)
        assert cfg.retry is not None
        self.assertEqual(cfg.retry.max_attempts, 3)

    def test_retry_rejects_a_non_policy(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig(id="k", retry=3)

    def test_are_excluded_from_the_config_dump(self) -> None:
        cfg = KnotConfig(id="k", timeout=1.0, retry=KnotRetryPolicy(max_attempts=2))
        dumped = cfg.model_dump(mode="json")
        self.assertNotIn("timeout", dumped)
        self.assertNotIn("retry", dumped)
        self.assertNotIn("timeout", cfg.model_dump_json())

    def test_config_hash_is_unchanged_from_before_the_fields_existed(self) -> None:
        minimal = KnotConfig(id="k", timeout=1.0, retry=KnotRetryPolicy(max_attempts=2))
        full = KnotConfig(
            id="llm0",
            error_policy=ErrorPolicy.RECEIVE_ERRORS,
            tags=("api",),
            description="call",
            timeout=30.0,
            retry=KnotRetryPolicy(max_attempts=4),
        )
        self.assertEqual(ContentHasher.hash(minimal.model_dump(mode="json")), self.golden_minimal)
        self.assertEqual(ContentHasher.hash(full.model_dump(mode="json")), self.golden_full)
