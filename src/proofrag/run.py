"""Prediction adapters for running a RAG app over a golden set.

This fills the hand-written driver gap: users can point proofrag at an HTTP
endpoint or a Python callable and get the `predictions.jsonl` contract that
`proofrag evaluate` already consumes.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Literal

from .goldenset import write_jsonl

CallStyle = Literal["question", "record"]
Runner = Callable[[dict[str, Any]], Any]


class RunError(RuntimeError):
    """Raised when a prediction adapter cannot produce a usable prediction."""


def load_callable(spec: str) -> Callable[..., Any]:
    """Load `module:function` or `module:object.method` into a callable."""
    module_name, sep, attr_path = spec.partition(":")
    if not sep or not module_name or not attr_path:
        raise RunError("callable must look like 'module:function' or 'module:object.method'")

    try:
        obj: Any = importlib.import_module(module_name)
    except Exception as e:  # noqa: BLE001 - preserve the import failure for the CLI
        raise RunError(f"could not import module {module_name!r}: {e}") from e

    for part in attr_path.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError as e:
            raise RunError(f"{spec!r} has no attribute {part!r}") from e
    if not callable(obj):
        raise RunError(f"{spec!r} is not callable")
    return obj


def callable_runner(spec: str, style: CallStyle = "question") -> Runner:
    """Build a runner from a Python callable.

    `question` style calls `fn(question)`. `record` style calls `fn(golden_record)`.
    The callable may be sync or async.
    """
    fn = load_callable(spec)

    def run(record: dict[str, Any]) -> Any:
        arg = record if style == "record" else str(record.get("question", ""))
        return _resolve(fn(arg))

    return run


def endpoint_runner(
    endpoint: str,
    *,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> Runner:
    """Build a runner that POSTs `{id, question}` JSON to an HTTP endpoint."""
    extra_headers = headers or {}

    def run(record: dict[str, Any]) -> Any:
        payload = {"id": record.get("id"), "question": record.get("question", "")}
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **extra_headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RunError(f"endpoint returned HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RunError(f"endpoint request failed: {e.reason}") from e

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    return run


def parse_headers(values: list[str] | None) -> dict[str, str]:
    """Parse repeated `--header 'Name: value'` flags."""
    headers: dict[str, str] = {}
    for value in values or []:
        name, sep, body = value.partition(":")
        if not sep or not name.strip():
            raise RunError(f"invalid header {value!r}; expected 'Name: value'")
        headers[name.strip()] = body.strip()
    return headers


def run_predictions(goldenset: list[dict[str, Any]], runner: Runner) -> list[dict[str, Any]]:
    """Run a prediction adapter over every golden record."""
    predictions: list[dict[str, Any]] = []
    for record in goldenset:
        raw = runner(record)
        predictions.append(normalize_prediction(record, raw))
    return predictions


def write_predictions(predictions: list[dict[str, Any]], path: str) -> None:
    """Write prediction records as JSONL."""
    write_jsonl(predictions, path)


def normalize_prediction(record: dict[str, Any], raw: Any) -> dict[str, Any]:
    """Normalize common adapter return shapes into proofrag's prediction schema.

    Accepted shapes:
    - `"answer text"`
    - `{"answer": "...", "retrieved_contexts": ["..."]}`
    - `{"output": "...", "contexts": ["..."]}`
    - `("answer text", ["context", "..."])`
    """
    answer: Any
    contexts: Any

    if isinstance(raw, dict):
        answer = raw.get("answer", raw.get("output", raw.get("response", "")))
        contexts = raw.get("retrieved_contexts", raw.get("contexts", raw.get("context", [])))
    elif isinstance(raw, str):
        answer = raw
        contexts = []
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        answer, contexts = raw
    else:
        raise RunError(
            "adapter must return a string, a dict with answer/retrieved_contexts, "
            "or a two-item (answer, contexts) tuple"
        )

    if contexts is None:
        context_list: list[str] = []
    elif isinstance(contexts, str):
        context_list = [contexts]
    else:
        try:
            context_list = [str(c) for c in contexts]
        except TypeError as e:
            raise RunError("retrieved_contexts must be a string or iterable of strings") from e

    return {
        "id": str(record["id"]),
        "answer": str(answer or ""),
        "retrieved_contexts": context_list,
    }


def _resolve(value: Any) -> Any:
    if inspect.iscoroutine(value):
        return asyncio.run(value)
    return value
