.PHONY: default install lint test build clean

default: install lint test

install:
	uv sync --all-extras

lint:
	uv run python devtools/lint.py

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest

build:
	uv build

upgrade:
	uv sync --upgrade --all-extras

clean:
	-rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .ruff_cache/ .coverage htmlcov/
	-find . -type d -name __pycache__ -exec rm -rf {} +
