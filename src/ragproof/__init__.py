"""ragproof: zero-config RAG/LLM evaluation — golden sets, LLM-as-judge, scorecards."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ragproof")
except PackageNotFoundError:  # running from a source tree without install metadata
    __version__ = "0+unknown"
