from pathlib import Path

import pytest


@pytest.fixture
def symlink_or_skip():
    """Create a symlink, skipping tests when Windows policy forbids it."""

    def create(link: Path, target: Path) -> None:
        try:
            link.symlink_to(target)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                pytest.skip("creating symlinks requires Windows Developer Mode or privileges")
            raise

    return create
