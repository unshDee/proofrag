"""Render a results dict into a self-contained, shareable HTML scorecard.

Zero external assets — inline CSS, no JS, no fonts fetched. Open the file
anywhere, attach it to a PR, drop it in CI artifacts. This is the artifact
people screenshot, so it is built to look good.
"""

from __future__ import annotations

import html
import json

from .judge import JUDGE_DIMENSIONS

_LABELS = {
    "groundedness": "Groundedness",
    "correctness": "Correctness",
    "completeness": "Completeness",
    "citation_quality": "Citation Quality",
    "retrieval_recall": "Retrieval Recall",
}


def _grade(v: float) -> str:
    if v >= 0.85:
        return "good"
    if v >= 0.65:
        return "ok"
    return "bad"


def _bar(label: str, value: float) -> str:
    pct = round(value * 100)
    return f"""
      <div class="metric">
        <div class="metric-head"><span>{html.escape(label)}</span><b>{pct}</b></div>
        <div class="track"><div class="fill {_grade(value)}" style="width:{pct}%"></div></div>
      </div>"""


def _card(label: str, value: float) -> str:
    pct = round(value * 100)
    return f"""
      <div class="card {_grade(value)}">
        <div class="card-val">{pct}</div>
        <div class="card-label">{html.escape(label)}</div>
      </div>"""


def _worst(records: list[dict], k: int = 8) -> list[dict]:
    def mean(r):
        s = r["scores"]
        return sum(s[d] for d in JUDGE_DIMENSIONS) / len(JUDGE_DIMENSIONS)
    return sorted(records, key=mean)[:k]


def render(results: dict) -> str:
    agg = results.get("aggregate", {})
    records = results.get("records", [])
    metrics = JUDGE_DIMENSIONS + ["retrieval_recall"]

    overall = (
        round(sum(agg.get(d, 0.0) for d in JUDGE_DIMENSIONS) / len(JUDGE_DIMENSIONS) * 100)
        if records else 0
    )
    cards = "".join(_card(_LABELS[m], agg.get(m, 0.0)) for m in metrics)
    bars = "".join(_bar(_LABELS[m], agg.get(m, 0.0)) for m in metrics)

    rows = []
    for r in _worst(records):
        s = r["scores"]
        cells = "".join(
            f'<td class="num {_grade(s[d])}">{round(s[d]*100)}</td>' for d in JUDGE_DIMENSIONS
        )
        rows.append(
            f"<tr><td class='q'>{html.escape(r['question'])}"
            f"<div class='why'>{html.escape(r.get('rationale',''))}</div></td>"
            f"<td><span class='tag'>{html.escape(r.get('difficulty',''))}</span></td>"
            f"{cells}"
            f"<td class='num {_grade(r['retrieval_recall'])}'>{round(r['retrieval_recall']*100)}</td></tr>"
        )
    failing = "".join(rows) or "<tr><td colspan='7'>No records.</td></tr>"

    return _TEMPLATE.format(
        overall=overall,
        overall_grade=_grade(overall / 100) if records else "bad",
        n=results.get("n", 0),
        judge=html.escape(results.get("judge_fingerprint", "unknown")),
        created=html.escape(results.get("created", "")),
        cards=cards,
        bars=bars,
        failing=failing,
    )


def write_html(results: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(results))


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG Eval Scorecard</title>
<style>
  :root {{
    --bg:#0b0e14; --panel:#141925; --line:#222b3a; --ink:#e6edf3; --mut:#8b98ad;
    --good:#3fb950; --ok:#d29922; --bad:#f85149;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:40px 24px 64px; }}
  header {{ display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px;
    border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:28px; }}
  h1 {{ margin:0; font-size:22px; letter-spacing:.2px; }}
  h1 .kit {{ color:var(--mut); font-weight:500; }}
  .meta {{ color:var(--mut); font-size:13px; text-align:right; }}
  .meta code {{ color:var(--ink); background:var(--panel); padding:2px 6px; border-radius:5px; }}
  .hero {{ display:flex; align-items:center; gap:24px; background:var(--panel);
    border:1px solid var(--line); border-radius:14px; padding:24px 28px; margin-bottom:24px; }}
  .ring {{ font-size:54px; font-weight:700; line-height:1; }}
  .ring.good {{ color:var(--good); }} .ring.ok {{ color:var(--ok); }} .ring.bad {{ color:var(--bad); }}
  .hero .sub {{ color:var(--mut); }}
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:28px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:16px; text-align:center; }}
  .card-val {{ font-size:30px; font-weight:700; }}
  .card-label {{ color:var(--mut); font-size:12px; margin-top:4px; }}
  .card.good .card-val {{ color:var(--good); }} .card.ok .card-val {{ color:var(--ok); }}
  .card.bad .card-val {{ color:var(--bad); }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:24px 28px; margin-bottom:24px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.8px; color:var(--mut);
    margin:0 0 18px; }}
  .metric {{ margin-bottom:14px; }}
  .metric-head {{ display:flex; justify-content:space-between; font-size:13px; margin-bottom:5px; }}
  .track {{ height:8px; background:#0b0e14; border-radius:6px; overflow:hidden; }}
  .fill {{ height:100%; border-radius:6px; }}
  .fill.good {{ background:var(--good); }} .fill.ok {{ background:var(--ok); }}
  .fill.bad {{ background:var(--bad); }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:right; color:var(--mut); font-weight:600; padding:8px 10px;
    border-bottom:1px solid var(--line); }}
  th:first-child {{ text-align:left; }}
  td {{ padding:11px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  td.q {{ max-width:380px; }}
  td.why {{ }}
  .why {{ color:var(--mut); font-size:12px; margin-top:4px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
  td.num.good {{ color:var(--good); }} td.num.ok {{ color:var(--ok); }} td.num.bad {{ color:var(--bad); }}
  .tag {{ background:#0b0e14; border:1px solid var(--line); color:var(--mut);
    font-size:11px; padding:2px 7px; border-radius:999px; white-space:nowrap; }}
  footer {{ color:var(--mut); font-size:12px; text-align:center; margin-top:32px; }}
  footer a {{ color:var(--mut); }}
  @media (max-width:720px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>RAG Eval Scorecard <span class="kit">· rag-eval-kit</span></h1>
    <div class="meta">judge <code>{judge}</code><br>{created} · {n} cases</div>
  </header>

  <div class="hero">
    <div class="ring {overall_grade}">{overall}</div>
    <div>
      <div style="font-size:18px;font-weight:600;">Overall generation quality</div>
      <div class="sub">Mean of groundedness, correctness, completeness & citation quality across {n} cases.</div>
    </div>
  </div>

  <div class="cards">{cards}</div>

  <div class="panel">
    <h2>Metrics</h2>
    {bars}
  </div>

  <div class="panel">
    <h2>Weakest cases</h2>
    <table>
      <thead><tr>
        <th>Question</th><th>Tier</th><th>Grnd</th><th>Corr</th><th>Comp</th><th>Cite</th><th>Recall</th>
      </tr></thead>
      <tbody>{failing}</tbody>
    </table>
  </div>

  <footer>Generated by <a href="https://github.com/unshDee/rag-eval-kit">rag-eval-kit</a> — point your agent at your docs, get a golden set + scorecard in one command.</footer>
</div></body></html>"""
