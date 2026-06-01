"""Render a results dict into a self-contained, shareable HTML scorecard.

Zero external assets — inline CSS, no JS, no fonts fetched. Open the file
anywhere, attach it to a PR, drop it in CI artifacts. This is the artifact
people screenshot, so it is built to look good.
"""

from __future__ import annotations

import html

from .judge import JUDGE_DIMENSIONS
from .metrics import RETRIEVAL_METRICS

_GEN_LABELS = {
    "groundedness": "Groundedness",
    "correctness": "Correctness",
    "completeness": "Completeness",
    "citation_quality": "Citation Quality",
}


def _ret_labels(k: int) -> dict:
    return {
        "recall_at_k": f"Recall@{k}",
        "precision_at_k": f"Precision@{k}",
        "ndcg_at_k": f"NDCG@{k}",
        "mrr": "MRR",
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


def _gen_mean(r: dict) -> float:
    s = r["scores"]
    return sum(s[d] for d in JUDGE_DIMENSIONS) / len(JUDGE_DIMENSIONS)


def _num_cell(value) -> str:
    if value is None:
        return '<td class="num mut">—</td>'
    return f'<td class="num {_grade(value)}">{round(value * 100)}</td>'


def render(results: dict) -> str:
    agg = results.get("aggregate", {})
    records = results.get("records", [])
    k = results.get("k", 5)
    ret_labels = _ret_labels(k)

    overall = (
        round(sum(agg.get(d, 0.0) for d in JUDGE_DIMENSIONS) / len(JUDGE_DIMENSIONS) * 100)
        if records
        else 0
    )
    # Headline cards: 4 generation dims + NDCG@k as the single best retrieval signal.
    cards = "".join(_card(_GEN_LABELS[d], agg.get(d, 0.0)) for d in JUDGE_DIMENSIONS)
    cards += _card(ret_labels["ndcg_at_k"], agg.get("ndcg_at_k", 0.0))

    gen_bars = "".join(_bar(_GEN_LABELS[d], agg.get(d, 0.0)) for d in JUDGE_DIMENSIONS)
    ret_bars = "".join(_bar(ret_labels[m], agg.get(m, 0.0)) for m in RETRIEVAL_METRICS)

    rows = []
    for r in sorted(records, key=_gen_mean)[:8]:
        s = r["scores"]
        cells = "".join(_num_cell(s[d]) for d in JUDGE_DIMENSIONS)
        ndcg = r["retrieval"]["ndcg_at_k"] if r.get("retrieval") else None
        rows.append(
            f"<tr><td class='q'>{html.escape(r['question'])}"
            f"<div class='why'>{html.escape(r.get('rationale', ''))}</div></td>"
            f"<td><span class='tag'>{html.escape(r.get('difficulty', ''))}</span></td>"
            f"{cells}{_num_cell(ndcg)}</tr>"
        )
    failing = "".join(rows) or "<tr><td colspan='7'>No records.</td></tr>"

    return _TEMPLATE.format(
        overall=overall,
        overall_grade=_grade(overall / 100) if records else "bad",
        n=results.get("n", 0),
        judge=html.escape(results.get("judge_fingerprint", "unknown")),
        created=html.escape(results.get("created", "")),
        ndcg_head=html.escape(ret_labels["ndcg_at_k"]),
        cards=cards,
        gen_bars=gen_bars,
        ret_bars=ret_bars,
        failing=failing,
    )


def write_html(results: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(results))


def _pct(v) -> str:
    return "—" if v is None else f"{round(v * 100)}"


def render_comparison(result: dict) -> str:
    """Render a blind A/B comparison (from compare.py) to self-contained HTML."""
    a = html.escape(result.get("a_name", "A"))
    b = html.escape(result.get("b_name", "B"))
    wins = result.get("wins", {"a": 0, "b": 0, "tie": 0})
    n = max(result.get("n", 0), 1)
    aw, bw, tw = wins.get("a", 0), wins.get("b", 0), wins.get("tie", 0)
    a_pct, b_pct = round(aw / n * 100), round(bw / n * 100)
    t_pct = max(0, 100 - a_pct - b_pct)
    verdict = f"{a} wins" if aw > bw else f"{b} wins" if bw > aw else "Too close to call"

    rlabels = _ret_labels(result.get("k", 5))
    ra, rb = result.get("retrieval_a", {}), result.get("retrieval_b", {})
    ret_rows = "".join(
        f"<tr><td>{html.escape(rlabels[m])}</td>"
        f"<td class='num'>{_pct(ra.get(m))}</td><td class='num'>{_pct(rb.get(m))}</td></tr>"
        for m in RETRIEVAL_METRICS
    )

    badge = {
        "a": f"<span class='win wa'>{a}</span>",
        "b": f"<span class='win wb'>{b}</span>",
        "tie": "<span class='win wt'>tie</span>",
    }
    rows = (
        "".join(
            f"<tr><td class='q'>{html.escape(r['question'])}"
            f"<div class='why'>{html.escape(r.get('reason', ''))}</div></td>"
            f"<td>{badge.get(r['winner'], '')}</td>"
            f"<td class='ans'>{html.escape(r.get('a_answer', '')[:240])}</td>"
            f"<td class='ans'>{html.escape(r.get('b_answer', '')[:240])}</td></tr>"
            for r in result.get("records", [])
        )
        or "<tr><td colspan='4'>No records.</td></tr>"
    )

    return _CMP_TEMPLATE.format(
        a=a,
        b=b,
        verdict=html.escape(verdict),
        n=result.get("n", 0),
        aw=aw,
        bw=bw,
        tw=tw,
        a_pct=a_pct,
        b_pct=b_pct,
        t_pct=t_pct,
        judge=html.escape(result.get("judge_fingerprint", "unknown")),
        created=html.escape(result.get("created", "")),
        ret_rows=ret_rows,
        rows=rows,
    )


def write_comparison_html(result: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_comparison(result))


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
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:16px; text-align:center; }}
  .card-val {{ font-size:30px; font-weight:700; }}
  .card-label {{ color:var(--mut); font-size:12px; margin-top:4px; }}
  .card.good .card-val {{ color:var(--good); }} .card.ok .card-val {{ color:var(--ok); }}
  .card.bad .card-val {{ color:var(--bad); }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px; }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:24px 28px; }}
  .panel.full {{ margin-bottom:24px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.8px; color:var(--mut);
    margin:0 0 18px; }}
  h2 small {{ text-transform:none; letter-spacing:0; font-weight:400; }}
  .metric {{ margin-bottom:14px; }}
  .metric:last-child {{ margin-bottom:0; }}
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
  .why {{ color:var(--mut); font-size:12px; margin-top:4px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
  td.num.good {{ color:var(--good); }} td.num.ok {{ color:var(--ok); }} td.num.bad {{ color:var(--bad); }}
  td.num.mut {{ color:var(--mut); }}
  .tag {{ background:#0b0e14; border:1px solid var(--line); color:var(--mut);
    font-size:11px; padding:2px 7px; border-radius:999px; white-space:nowrap; }}
  footer {{ color:var(--mut); font-size:12px; text-align:center; margin-top:32px; }}
  footer a {{ color:var(--mut); }}
  @media (max-width:720px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} .grid2 {{ grid-template-columns:1fr; }} }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>RAG Eval Scorecard <span class="kit">· proofrag</span></h1>
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

  <div class="grid2">
    <div class="panel">
      <h2>Generation <small>— LLM-as-judge</small></h2>
      {gen_bars}
    </div>
    <div class="panel">
      <h2>Retrieval <small>— rank-aware</small></h2>
      {ret_bars}
    </div>
  </div>

  <div class="panel full">
    <h2>Weakest cases</h2>
    <table>
      <thead><tr>
        <th>Question</th><th>Tier</th><th>Grnd</th><th>Corr</th><th>Comp</th><th>Cite</th><th>{ndcg_head}</th>
      </tr></thead>
      <tbody>{failing}</tbody>
    </table>
  </div>

  <footer>Generated by <a href="https://github.com/unshDee/proofrag">proofrag</a> — point your agent at your docs, get a golden set + scorecard in one command.</footer>
</div></body></html>"""


_CMP_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG A/B — proofrag</title>
<style>
  :root {{
    --bg:#0b0e14; --panel:#141925; --line:#222b3a; --ink:#e6edf3; --mut:#8b98ad;
    --a:#3b82f6; --b:#a855f7; --tie:#3a4456;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:40px 24px 64px; }}
  header {{ display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px;
    border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:28px; }}
  h1 {{ margin:0; font-size:22px; }} h1 .kit {{ color:var(--mut); font-weight:500; }}
  .meta {{ color:var(--mut); font-size:13px; text-align:right; }}
  .meta code {{ color:var(--ink); background:var(--panel); padding:2px 6px; border-radius:5px; }}
  .hero {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:24px 28px; margin-bottom:24px; }}
  .verdict {{ font-size:22px; font-weight:700; margin-bottom:6px; }}
  .legend {{ color:var(--mut); font-size:13px; margin-bottom:16px; }}
  .legend b.wa {{ color:var(--a); }} .legend b.wb {{ color:var(--b); }}
  .winbar {{ display:flex; height:34px; border-radius:8px; overflow:hidden; font-size:12px;
    font-weight:700; color:#0b0e14; }}
  .winbar .seg {{ display:flex; align-items:center; justify-content:center; min-width:0; }}
  .winbar .sa {{ background:var(--a); }} .winbar .sb {{ background:var(--b); }}
  .winbar .st {{ background:var(--tie); color:var(--mut); }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:24px 28px; margin-bottom:24px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.8px; color:var(--mut); margin:0 0 16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:right; color:var(--mut); font-weight:600; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th:first-child {{ text-align:left; }}
  td {{ padding:11px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
  td.q {{ max-width:300px; }} td.ans {{ color:var(--mut); font-size:12px; max-width:240px; }}
  .why {{ color:var(--mut); font-size:12px; margin-top:4px; }}
  .win {{ font-size:11px; font-weight:700; padding:2px 9px; border-radius:999px; white-space:nowrap; color:#0b0e14; }}
  .win.wa {{ background:var(--a); }} .win.wb {{ background:var(--b); }}
  .win.wt {{ background:var(--tie); color:var(--mut); }}
  footer {{ color:var(--mut); font-size:12px; text-align:center; margin-top:32px; }}
  footer a {{ color:var(--mut); }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>RAG A/B — blind <span class="kit">· proofrag</span></h1>
    <div class="meta">judge <code>{judge}</code><br>{created} · {n} cases</div>
  </header>

  <div class="hero">
    <div class="verdict">{verdict}</div>
    <div class="legend"><b class="wa">{a}</b> {aw} · tie {tw} · <b class="wb">{b}</b> {bw}
      &nbsp;— blind pairwise judging, answers shown in randomized order.</div>
    <div class="winbar">
      <div class="seg sa" style="width:{a_pct}%">{a_pct}%</div>
      <div class="seg st" style="width:{t_pct}%"></div>
      <div class="seg sb" style="width:{b_pct}%">{b_pct}%</div>
    </div>
  </div>

  <div class="panel">
    <h2>Retrieval (deterministic)</h2>
    <table>
      <thead><tr><th>Metric</th><th>{a}</th><th>{b}</th></tr></thead>
      <tbody>{ret_rows}</tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Per-question verdicts</h2>
    <table>
      <thead><tr><th>Question</th><th>Winner</th><th>{a}</th><th>{b}</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <footer>Generated by <a href="https://github.com/unshDee/proofrag">proofrag</a> — blind A/B comparison of two RAG variants.</footer>
</div></body></html>"""
