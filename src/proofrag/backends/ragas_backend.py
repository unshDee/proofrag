"""Ragas scoring backend (verified against ragas 0.4.3).

Maps proofrag's records onto Ragas single-turn samples and metrics:
  - faithfulness        -> answer grounded in retrieved context
  - answer_relevancy    -> answer addresses the question (requires embeddings)
  - factual_correctness -> answer matches the reference answer

Ragas generation metrics are combined with proofrag's own deterministic retrieval
metrics so scorecards, summaries, diffing, and CI gates stay unchanged.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import math
import os
import warnings
from typing import Any

from ..embeddings import DEFAULT_EMBED_MODEL
from ..goldenset import goldenset_fingerprint
from ..llm import LLM, LLMError, openai_client
from ..metrics import (
    RETRIEVAL_METRICS,
    lexical_matcher,
    matcher_fingerprint,
    retrieval_metrics,
)
from ..run import join_predictions
from . import BackendError

GENERATION_METRICS = ["faithfulness", "answer_relevancy", "factual_correctness"]


class _ProofragRagasLLM:
    """Small Ragas LLM wrapper backed by proofrag's provider abstraction."""

    def __init__(self, llm: LLM):
        try:
            from langchain_core.outputs import Generation, LLMResult
            from ragas.llms.base import BaseRagasLLM
        except ImportError as e:  # pragma: no cover - import guard
            raise BackendError("Ragas backend needs: pip install 'proofrag[ragas]'") from e

        class ProofragRagasLLM(BaseRagasLLM):
            def generate_text(
                self,
                prompt,
                n: int = 1,
                temperature: float | None = 0.01,
                stop: list[str] | None = None,
                callbacks=None,
            ) -> Any:
                text = prompt.to_string() if hasattr(prompt, "to_string") else str(prompt)
                generations = []
                for _ in range(n):
                    out = llm._complete(  # noqa: SLF001 - backend adapter for Ragas prompts
                        "You are a careful evaluator. Follow the prompt exactly.",
                        text,
                    )
                    generations.append(
                        Generation(text=out, generation_info={"finish_reason": "stop"})
                    )
                return LLMResult(generations=[generations])

            async def agenerate_text(
                self,
                prompt,
                n: int = 1,
                temperature: float | None = 0.01,
                stop: list[str] | None = None,
                callbacks=None,
            ) -> Any:
                return await asyncio.to_thread(
                    self.generate_text,
                    prompt,
                    n=n,
                    temperature=temperature,
                    stop=stop,
                    callbacks=callbacks,
                )

            def is_finished(self, response: Any) -> bool:
                return True

        self.inner = ProofragRagasLLM()


class _ProofragRagasEmbeddings:
    """Ragas embedding wrapper using proofrag's OpenAI-compatible embedding path."""

    def __init__(self):
        try:
            from ragas.embeddings.base import BaseRagasEmbeddings
        except ImportError as e:  # pragma: no cover - import guard
            raise BackendError("Ragas backend needs: pip install 'proofrag[ragas]'") from e

        client = openai_client()
        model = os.environ.get("PROOFRAG_EMBED_MODEL") or DEFAULT_EMBED_MODEL

        class ProofragRagasEmbeddings(BaseRagasEmbeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                resp = client.embeddings.create(model=model, input=[t[:2000] for t in texts])
                return [row.embedding for row in resp.data]

            def embed_query(self, text: str) -> list[float]:
                return self.embed_documents([text])[0]

            async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
                return await asyncio.to_thread(self.embed_documents, texts)

            async def aembed_query(self, text: str) -> list[float]:
                return await asyncio.to_thread(self.embed_query, text)

        self.inner = ProofragRagasEmbeddings()


def evaluate_ragas(
    goldenset: list[dict],
    predictions: list[dict],
    model: str | None = None,
    k: int = 5,
    matcher=None,
) -> dict:
    """Score predictions with Ragas metrics; keep proofrag retrieval metrics."""
    if k <= 0:
        raise ValueError("k must be greater than zero")
    cfg = LLM(model=model)
    llm = _ProofragRagasLLM(cfg).inner
    embeddings = _ragas_embeddings()
    metrics, generation_metrics = _build_metrics(llm, embeddings)

    samples, joined = _samples(goldenset, predictions)
    result = _evaluate_ragas_dataset(samples, metrics)
    rows = list(getattr(result, "scores", []))
    if len(rows) != len(joined):
        raise BackendError(f"Ragas returned {len(rows)} scores for {len(joined)} cases")

    matcher = matcher or lexical_matcher()
    records: list[dict] = []
    errors: list[dict[str, str]] = []
    for (g, pred), row in zip(joined, rows, strict=True):
        answer = pred.get("answer", "")
        retrieved = pred.get("retrieved_contexts", []) or []
        scores = {metric: _score(row.get(metric)) for metric in generation_metrics}
        if not retrieved and "faithfulness" in scores:
            scores["faithfulness"] = None
        for metric, score in scores.items():
            if score is None and not (metric == "faithfulness" and not retrieved):
                errors.append({"id": str(g["id"]), "error": f"{metric} unavailable"})
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
                "rationale": _rationale(scores),
            }
        )

    return {
        "judge_fingerprint": f"ragas/{cfg.fingerprint}",
        "backend": "ragas",
        "generation_metrics": generation_metrics,
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "k": k,
        "matcher": matcher_fingerprint(matcher),
        "goldenset_fingerprint": goldenset_fingerprint(goldenset),
        "n": len(records),
        "evaluation_errors": errors,
        "aggregate": _aggregate(records, generation_metrics),
        "records": records,
    }


def _ragas_embeddings():
    try:
        return _ProofragRagasEmbeddings().inner
    except LLMError:
        return None


def _build_metrics(llm, embeddings) -> tuple[list[Any], list[str]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from ragas.metrics import FactualCorrectness, Faithfulness, ResponseRelevancy
    except ImportError as e:  # pragma: no cover - import guard
        raise BackendError("Ragas backend needs: pip install 'proofrag[ragas]'") from e

    metrics: list[Any] = [Faithfulness(llm=llm), FactualCorrectness(llm=llm)]
    names = ["faithfulness", "factual_correctness"]
    if embeddings is not None:
        metrics.insert(1, ResponseRelevancy(llm=llm, embeddings=embeddings))
        names.insert(1, "answer_relevancy")
    return metrics, names


def _samples(
    goldenset: list[dict], predictions: list[dict]
) -> tuple[list[Any], list[tuple[dict, dict]]]:
    try:
        from ragas.dataset_schema import SingleTurnSample
    except ImportError as e:  # pragma: no cover - import guard
        raise BackendError("Ragas backend needs: pip install 'proofrag[ragas]'") from e

    samples: list[Any] = []
    joined: list[tuple[dict, dict]] = []
    for g, pred in join_predictions(goldenset, predictions):
        retrieved = pred.get("retrieved_contexts", []) or []
        sample = SingleTurnSample(
            user_input=g["question"],
            response=pred.get("answer", "") or "(no answer)",
            reference=g.get("gold_answer", ""),
            retrieved_contexts=retrieved or ["(no context retrieved)"],
            reference_contexts=g.get("gold_contexts", []) or [],
        )
        samples.append(sample)
        joined.append((g, pred))
    return samples, joined


def _evaluate_ragas_dataset(samples: list[Any], metrics: list[Any]):
    try:
        from ragas import EvaluationDataset, evaluate
    except ImportError as e:  # pragma: no cover - import guard
        raise BackendError("Ragas backend needs: pip install 'proofrag[ragas]'") from e
    return evaluate(
        EvaluationDataset(samples=samples),
        metrics=metrics,
        raise_exceptions=False,
        show_progress=False,
    )


def _score(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score):
        return None
    return round(max(0.0, min(1.0, score)), 3)


def _rationale(scores: dict[str, float | None]) -> str:
    unavailable = [metric.replace("_", " ") for metric, score in scores.items() if score is None]
    if unavailable:
        return "Unavailable Ragas metrics: " + ", ".join(unavailable) + "."
    return ""


def _aggregate(records: list[dict], generation_metrics: list[str]) -> dict:
    agg: dict[str, float] = {}
    for m in generation_metrics:
        vals = [r["scores"][m] for r in records if r["scores"].get(m) is not None]
        agg[m] = round(sum(vals) / len(vals), 3) if vals else 0.0
    rets = [r["retrieval"] for r in records if r.get("retrieval")]
    for m in RETRIEVAL_METRICS:
        vals = [rt[m] for rt in rets if rt.get(m) is not None]
        agg[m] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return agg
