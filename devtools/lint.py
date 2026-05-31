#!/usr/bin/env python3
"""Run all lint / format / type-check tools in one shot (used by `make lint`)."""

from __future__ import annotations

import subprocess
import sys

TARGETS = ["src", "tests", "devtools"]


def run(cmd: list[str]) -> int:
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> None:
    rc = 0
    rc |= run(["ruff", "check", "--fix", *TARGETS])
    rc |= run(["ruff", "format", *TARGETS])
    rc |= run(["codespell", "--write-changes", "src", "tests"])
    rc |= run(["basedpyright", "src", "tests"])
    sys.exit(1 if rc else 0)


if __name__ == "__main__":
    main()
