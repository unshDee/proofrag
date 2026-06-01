"""DeepEval scoring backend (verified against deepeval 4.0.5).

Maps proofrag's records onto DeepEval test cases and metrics:
  - faithfulness      -> FaithfulnessMetric   (answer grounded in retrieved context)
  - answer_relevancy  -> AnswerRelevancyMetric (answer addresses the question)
  - correctness       -> GEval vs the gold answer

The judge model is taken from proofrag's provider/model config: Anthropic ->
AnthropicModel, OpenAI -> GPTModel. Retrieval metrics stay proofrag's own.
"""

from __future__ import annotations

import datetime as _dt
import os

from ..llm import LLM
from ..metrics import RETRIEVAL_METRICS, lexical_matcher, retrieval_metrics
from . import BackendError

GENERATION_METRICS = ["faithfulness", "answer_relevancy", "correctness"]


def _deepeval_model(provider: str, model: str):
    try:
        from deepeval.models import AnthropicModel, GPTModel
    except ImportError as e:  # pragma: no cover - import guard
        raise BackendError("DeepEval backend needs: pip install 'proofrag[deepeval]'") from e
    if provider == "anthropic":
        return AnthropicModel(model=model)
    if provider == "openai":
        # GPTModel honors base_url, so this also covers local/compatible endpoints.
        base = os.environ.get("OPENAI_BASE_URL")
        key = os.environ.get("OPENAI_API_KEY") or ("not-needed" if base else None)
        return GPTModel(model=model, base_url=base, api_key=key)
    raise BackendError(f"DeepEval backend supports anthropic/openai, not {provider!r}")


def _build_metrics(model):
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
    from deepeval.test_case import SingleTurnParams as P

    common = {"model": model, "async_mode": False, "verbose_mode": False}
    faith = FaithfulnessMetric(include_reason=False, **common)
    rel = AnswerRelevancyMetric(include_reason=False, **common)
    corr = GEval(
        name="Correctness",
        criteria="Is the actual output factually correct and complete relative to the expected output?",
        evaluation_params=[P.INPUT, P.ACTUAL_OUTPUT, P.EXPECTED_OUTPUT],
        model=model,
        async_mode=False,
    )
    return faith, rel, corr


def _measure(metric, tc):
    try:
        metric.measure(tc)
        return round(float(metric.score), 3)
    except Exception:  # noqa: BLE001 - one metric failing shouldn't abort the run
        return None


def evaluate_deepeval(
    goldenset: list[dict],
    predictions: list[dict],
    model: str | None = None,
    k: int = 5,
    matcher=None,
) -> dict:
    """Score predictions with DeepEval metrics; keep proofrag retrieval metrics."""
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    cfg = LLM(model=model)  # resolves provider/model from env, no SDK import
    dm = _deepeval_model(cfg.provider, cfg.model)

    from deepeval.test_case import LLMTestCase

    matcher = matcher or lexical_matcher()
    faith, rel, corr = _build_metrics(dm)
    preds = {p["id"]: p for p in predictions}

    records: list[dict] = []
    for g in goldenset:
        pred = preds.get(g["id"])
        if pred is None:
            continue
        answer = pred.get("answer", "")
        retrieved = pred.get("retrieved_contexts", []) or []
        tc = LLMTestCase(
            input=g["question"],
            actual_output=answer or "(no answer)",
            expected_output=g.get("gold_answer", ""),
            retrieval_context=retrieved or ["(no context retrieved)"],
        )
        scores = {
            "faithfulness": _measure(faith, tc) if retrieved else None,
            "answer_relevancy": _measure(rel, tc),
            "correctness": _measure(corr, tc),
        }
        records.append(
            {
                "id": g["id"],
                "question": g["question"],
                "difficulty": g.get("difficulty", "single_doc"),
                "answer": answer,
                "scores": scores,
                "retrieval": (
                    retrieval_metrics(g.get("gold_contexts", []), retrieved, k, matcher)
                    if g.get("gold_contexts")
                    else None
                ),
                "rationale": "",
            }
        )

    return {
        "judge_fingerprint": f"deepeval/{cfg.provider}:{cfg.model}",
        "backend": "deepeval",
        "generation_metrics": list(GENERATION_METRICS),
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "k": k,
        "n": len(records),
        "aggregate": _aggregate(records),
        "records": records,
    }


def _aggregate(records: list[dict]) -> dict:
    agg: dict[str, float] = {}
    for m in GENERATION_METRICS:
        vals = [r["scores"][m] for r in records if r["scores"].get(m) is not None]
        agg[m] = round(sum(vals) / len(vals), 3) if vals else 0.0
    rets = [r["retrieval"] for r in records if r.get("retrieval")]
    for m in RETRIEVAL_METRICS:
        vals = [rt[m] for rt in rets if rt.get(m) is not None]
        agg[m] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return agg
