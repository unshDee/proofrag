#!/usr/bin/env python3
"""Run all lint / format / type-check tools in one shot (used by `make lint`)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TARGETS = [
    target for target in ["src", "tests", "devtools", "case_studies"] if Path(target).exists()
]
SPELL_TARGETS = [
    *TARGETS,
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    ".env.example",
    "action.yml",
    "commands",
    "skills",
]


def run(cmd: list[str]) -> int:
    print(f"\n>> {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd)


def main() -> None:
    rc = 0
    rc |= run(["ruff", "check", *TARGETS])
    rc |= run(["ruff", "format", "--check", *TARGETS])
    rc |= run(["codespell", *SPELL_TARGETS])
    rc |= run(["basedpyright", *TARGETS])
    sys.exit(1 if rc else 0)


if __name__ == "__main__":
    main()
