#!/usr/bin/env python3
"""
Derived version calculator for pirn — trunk-based development.

Version schema: MAJOR.MINOR.PATCH[.devRUN]

  MAJOR  — hardcoded in CI env (bump for breaking changes)
  MINOR  — latest MINOR on PyPI for that MAJOR + 1
  PATCH  — PR number (or 0 for direct main pushes)
  .devRUN — GitHub run number, appended only for TestPyPI preview builds

PyPI is queried at build time. If the package has never been published,
MINOR starts at 0.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime


PACKAGE_NAME = os.environ.get("PACKAGE_NAME", "pirn").strip()
MAJOR_VERSION = int(os.environ.get("MAJOR_VERSION", "0").strip() or "0")
GITHUB_REF = os.environ.get("GITHUB_REF", "").strip()
GITHUB_SHA = os.environ.get("GITHUB_SHA", "").strip()
GITHUB_RUN_NUMBER = os.environ.get("GITHUB_RUN_NUMBER", "").strip()
GITHUB_EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "push").strip()
GITHUB_BASE_REF = os.environ.get("GITHUB_BASE_REF", "").strip()
GITHUB_EVENT_ACTION = os.environ.get("GITHUB_EVENT_ACTION", "").strip()


def get_pypi_version(package: str) -> tuple[int, int] | None:
    """Return (major, minor) of the latest published release, or None."""
    url = f"https://pypi.org/pypi/{package}/json"
    print(f"Querying PyPI: {url}")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        version = data["info"]["version"]
        m = re.match(r"^(\d+)\.(\d+)", version)
        if not m:
            print(f"Could not parse PyPI version {version!r}", file=sys.stderr)
            return None
        return int(m.group(1)), int(m.group(2))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("Package not yet on PyPI — first release")
            return None
        print(f"PyPI query failed ({exc.code}): {exc}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"PyPI query failed: {exc}", file=sys.stderr)
        return None


def extract_pr_number(ref: str) -> str | None:
    m = re.search(r"refs/pull/(\d+)/", ref)
    return m.group(1) if m else None


def calculate_version() -> tuple[str, bool, bool]:
    """Return (version, should_publish_testpypi, should_publish_pypi)."""
    is_pr = GITHUB_EVENT_NAME == "pull_request"
    is_pr_to_main = GITHUB_BASE_REF in ("main", "refs/heads/main")
    is_main_push = GITHUB_EVENT_NAME == "push" and GITHUB_REF == "refs/heads/main"

    pr_number = extract_pr_number(GITHUB_REF) if is_pr else None

    should_publish_testpypi = is_pr and is_pr_to_main and GITHUB_EVENT_ACTION != "closed"
    should_publish_pypi = (
        (is_pr and GITHUB_EVENT_ACTION == "closed" and is_pr_to_main)
        or is_main_push
    )

    pypi = get_pypi_version(PACKAGE_NAME)
    if pypi is None:
        new_minor = 0
    else:
        pypi_major, pypi_minor = pypi
        new_minor = (pypi_minor + 1) if pypi_major == MAJOR_VERSION else 1

    if is_main_push:
        version = f"{MAJOR_VERSION}.{new_minor}.0"
    elif is_pr and pr_number:
        version = f"{MAJOR_VERSION}.{new_minor}.{pr_number}"
        if should_publish_testpypi and GITHUB_RUN_NUMBER:
            version = f"{version}.dev{GITHUB_RUN_NUMBER}"
    else:
        # Feature branch push — dev version with timestamp
        stamp = datetime.now().strftime("%H%M%S")
        version = f"{MAJOR_VERSION}.{new_minor}.0.dev{stamp}"

    print(f"GITHUB_REF={GITHUB_REF!r} EVENT={GITHUB_EVENT_NAME!r} "
          f"ACTION={GITHUB_EVENT_ACTION!r} BASE={GITHUB_BASE_REF!r}")
    print(f"is_pr={is_pr} pr_to_main={is_pr_to_main} pr_number={pr_number}")
    print(f"testpypi={should_publish_testpypi} pypi={should_publish_pypi}")
    print(f"Version: {version}")

    return version, should_publish_testpypi, should_publish_pypi


def main():
    version, testpypi, pypi = calculate_version()

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"version={version}\n")
            f.write(f"should_publish_testpypi={str(testpypi).lower()}\n")
            f.write(f"should_publish_pypi={str(pypi).lower()}\n")

    return version


if __name__ == "__main__":
    main()
