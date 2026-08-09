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
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "relevancy": "Relevancy",
}

_GEN_SHORT = {
    "groundedness": "Grnd",
    "correctness": "Corr",
    "completeness": "Comp",
    "citation_quality": "Cite",
    "faithfulness": "Faith",
    "answer_relevancy": "Rel",
    "relevancy": "Rel",
}


def _gen_label(name: str) -> str:
    return _GEN_LABELS.get(name, name.replace("_", " ").title())


def _gen_short(name: str) -> str:
    return _GEN_SHORT.get(name, _gen_label(name)[:5])


def _gen_metrics(results: dict) -> list[str]:
    """Generation metric names for this run — backend-dependent, with a fallback."""
    return [str(name) for name in (results.get("generation_metrics") or JUDGE_DIMENSIONS)]


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
    g = _grade(value)
    return f"""
      <div class="metric">
        <div class="metric-head"><span>{html.escape(label)}</span><b class="{g}">{pct}</b></div>
        <div class="track"><div class="fill {g}" style="width:{pct}%"></div></div>
      </div>"""


def _card(label: str, value: float) -> str:
    pct = round(value * 100)
    g = _grade(value)
    return f"""
      <div class="card {g}">
        <div class="card-val">{pct}</div>
        <div class="card-label"><span class="dot"></span>{html.escape(label)}</div>
      </div>"""


def _num_cell(value) -> str:
    if value is None:
        return '<td class="num mut">—</td>'
    return f'<td class="num {_grade(value)}">{round(value * 100)}</td>'


def render(results: dict) -> str:
    agg = results.get("aggregate", {})
    records = results.get("records", [])
    k = results.get("k", 5)
    ret_labels = _ret_labels(k)
    gen = _gen_metrics(results)

    overall = round(sum(agg.get(d, 0.0) for d in gen) / len(gen) * 100) if records and gen else 0
    # Headline cards: each generation metric + NDCG@k as the single best retrieval signal.
    cards = "".join(_card(_gen_label(d), agg.get(d, 0.0)) for d in gen)
    cards += _card(ret_labels["ndcg_at_k"], agg.get("ndcg_at_k", 0.0))

    gen_bars = "".join(_bar(_gen_label(d), agg.get(d, 0.0)) for d in gen)
    ret_bars = "".join(_bar(ret_labels[m], agg.get(m, 0.0)) for m in RETRIEVAL_METRICS)
    gen_heads = "".join(f"<th>{html.escape(_gen_short(d))}</th>" for d in gen)

    def gmean(r: dict) -> float:
        s = r["scores"]
        vals = [s[d] for d in gen if s.get(d) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    rows = []
    for r in sorted(records, key=gmean)[:8]:
        s = r["scores"]
        cells = "".join(_num_cell(s.get(d)) for d in gen)
        ndcg = r["retrieval"]["ndcg_at_k"] if r.get("retrieval") else None
        rows.append(
            f"<tr><td class='q'>{html.escape(str(r['question']))}"
            f"<div class='why'>{html.escape(str(r.get('rationale', '')))}</div></td>"
            f"<td><span class='tag'>{html.escape(str(r.get('difficulty', '')))}</span></td>"
            f"{cells}{_num_cell(ndcg)}</tr>"
        )
    failing = "".join(rows) or f"<tr><td colspan='{len(gen) + 2}'>No records.</td></tr>"

    return _TEMPLATE.format(
        overall=overall,
        overall_grade=_grade(overall / 100) if records else "bad",
        n=results.get("n", 0),
        judge=html.escape(str(results.get("judge_fingerprint", "unknown"))),
        created=html.escape(str(results.get("created", ""))),
        backend=html.escape(str(results.get("backend", "proofrag"))),
        gen_names=html.escape(", ".join(_gen_label(d).lower() for d in gen)),
        ndcg_head=html.escape(ret_labels["ndcg_at_k"]),
        cards=cards,
        gen_bars=gen_bars,
        ret_bars=ret_bars,
        gen_heads=gen_heads,
        failing=failing,
    )


def write_html(results: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(results))


def _pct(v) -> str:
    return "—" if v is None else f"{round(v * 100)}"


def render_comparison(result: dict) -> str:
    """Render a blind A/B comparison (from compare.py) to self-contained HTML."""
    a = html.escape(str(result.get("a_name", "A")))
    b = html.escape(str(result.get("b_name", "B")))
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
            f"<tr><td class='q'>{html.escape(str(r['question']))}"
            f"<div class='why'>{html.escape(str(r.get('reason', '')))}</div></td>"
            f"<td>{badge.get(r['winner'], '')}</td>"
            f"<td class='ans'>{html.escape(str(r.get('a_answer', ''))[:240])}</td>"
            f"<td class='ans'>{html.escape(str(r.get('b_answer', ''))[:240])}</td></tr>"
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
        judge=html.escape(str(result.get("judge_fingerprint", "unknown"))),
        created=html.escape(str(result.get("created", ""))),
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
    --background:hsl(0 0% 100%); --foreground:hsl(240 10% 3.9%);
    --card:hsl(0 0% 100%); --muted:hsl(240 4.8% 95.9%);
    --muted-foreground:hsl(240 3.8% 46.1%); --border:hsl(240 5.9% 90%);
    --accent:hsl(240 4.8% 95.9%); --primary:hsl(240 5.9% 10%);
    --good:hsl(142 71% 35%); --ok:hsl(38 92% 40%); --bad:hsl(0 72% 48%);
    --radius:0.625rem;
    --shadow:0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.04);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--background); color:var(--foreground);
    -webkit-font-smoothing:antialiased;
    font:14.5px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:48px 28px 72px; }}
  .mono {{ font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace; }}
  header {{ display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:16px;
    margin-bottom:32px; }}
  h1 {{ margin:0; font-size:19px; font-weight:600; letter-spacing:-.01em; }}
  h1 .kit {{ color:var(--muted-foreground); font-weight:400; }}
  .tagline {{ color:var(--muted-foreground); font-size:13px; margin-top:4px; }}
  .meta {{ color:var(--muted-foreground); font-size:12.5px; text-align:right; line-height:1.7; }}
  .meta code {{ color:var(--foreground); background:var(--muted); padding:2px 7px; border-radius:6px;
    font-size:12px; }}
  .hero {{ display:flex; align-items:center; gap:28px; background:var(--card);
    border:1px solid var(--border); border-radius:var(--radius); padding:28px 32px;
    margin-bottom:20px; box-shadow:var(--shadow); }}
  .ring {{ font-size:52px; font-weight:680; line-height:1; letter-spacing:-.03em;
    font-variant-numeric:tabular-nums; }}
  .ring small {{ font-size:20px; color:var(--muted-foreground); font-weight:500; margin-left:2px; }}
  .ring.bad {{ color:var(--bad); }}
  .hero .htitle {{ font-size:16px; font-weight:600; }}
  .hero .sub {{ color:var(--muted-foreground); font-size:13.5px; margin-top:3px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:20px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
    padding:18px 16px; box-shadow:var(--shadow); }}
  .card-val {{ font-size:28px; font-weight:650; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }}
  .card-val small {{ font-size:14px; color:var(--muted-foreground); font-weight:500; }}
  .card-label {{ color:var(--muted-foreground); font-size:12.5px; margin-top:6px;
    display:flex; align-items:center; gap:6px; }}
  .dot {{ width:7px; height:7px; border-radius:999px; background:var(--good); flex:none; }}
  .ok .dot {{ background:var(--ok); }} .bad .dot {{ background:var(--bad); }}
  .bad .card-val {{ color:var(--bad); }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }}
  .panel {{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
    padding:24px 26px; box-shadow:var(--shadow); }}
  .panel.full {{ margin-bottom:20px; padding:24px 26px 12px; }}
  h2 {{ font-size:13px; font-weight:600; letter-spacing:-.005em; color:var(--foreground);
    margin:0 0 20px; }}
  h2 small {{ color:var(--muted-foreground); font-weight:400; }}
  .metric {{ margin-bottom:16px; }}
  .metric:last-child {{ margin-bottom:0; }}
  .metric-head {{ display:flex; justify-content:space-between; font-size:13px; margin-bottom:7px; }}
  .metric-head b {{ font-variant-numeric:tabular-nums; font-weight:600; }}
  .metric-head .bad {{ color:var(--bad); }}
  .track {{ height:6px; background:var(--muted); border-radius:999px; overflow:hidden; }}
  .fill {{ height:100%; border-radius:999px; background:var(--primary); }}
  .fill.bad {{ background:var(--bad); }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:right; color:var(--muted-foreground); font-weight:500; padding:0 12px 10px;
    border-bottom:1px solid var(--border); font-size:12px; }}
  th:first-child {{ text-align:left; }}
  td {{ padding:13px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
  tbody tr:last-child td {{ border-bottom:none; }}
  td.q {{ max-width:420px; font-weight:500; }}
  .why {{ color:var(--muted-foreground); font-size:12.5px; font-weight:400; margin-top:4px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:500; }}
  td.num.bad {{ color:var(--bad); font-weight:600; }}
  td.num.mut {{ color:var(--muted-foreground); }}
  .tag {{ background:var(--muted); color:var(--muted-foreground); font-weight:500;
    font-size:11px; padding:2px 9px; border-radius:6px; white-space:nowrap; }}
  footer {{ color:var(--muted-foreground); font-size:12.5px; text-align:center; margin-top:36px; }}
  footer a {{ color:var(--foreground); text-decoration:none; }}
  footer a:hover {{ text-decoration:underline; }}
  @media (max-width:720px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
</style></head>
<body><div class="wrap">
  <header>
    <div>
      <h1>RAG Eval Scorecard <span class="kit">· proofrag</span></h1>
      <div class="tagline">Generation quality &amp; retrieval, judged across {n} cases.</div>
    </div>
    <div class="meta">judge <code class="mono">{judge}</code><br>{created} · {n} cases</div>
  </header>

  <div class="hero">
    <div class="ring {overall_grade}">{overall}<small>/100</small></div>
    <div>
      <div class="htitle">Overall generation quality</div>
      <div class="sub">Mean of {gen_names} across {n} cases.</div>
    </div>
  </div>

  <div class="cards">{cards}</div>

  <div class="grid2">
    <div class="panel">
      <h2>Generation <small>— {backend}</small></h2>
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
        <th>Question</th><th>Tier</th>{gen_heads}<th>{ndcg_head}</th>
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
    --background:hsl(0 0% 100%); --foreground:hsl(240 10% 3.9%);
    --card:hsl(0 0% 100%); --muted:hsl(240 4.8% 95.9%);
    --muted-foreground:hsl(240 3.8% 46.1%); --border:hsl(240 5.9% 90%);
    --a:hsl(240 5.9% 10%); --b:hsl(217 91% 53%); --tie:hsl(240 4.8% 88%);
    --radius:0.625rem;
    --shadow:0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.04);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--background); color:var(--foreground);
    -webkit-font-smoothing:antialiased;
    font:14.5px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:48px 28px 72px; }}
  .mono {{ font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace; }}
  header {{ display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:16px;
    margin-bottom:32px; }}
  h1 {{ margin:0; font-size:19px; font-weight:600; letter-spacing:-.01em; }}
  h1 .kit {{ color:var(--muted-foreground); font-weight:400; }}
  .tagline {{ color:var(--muted-foreground); font-size:13px; margin-top:4px; }}
  .meta {{ color:var(--muted-foreground); font-size:12.5px; text-align:right; line-height:1.7; }}
  .meta code {{ color:var(--foreground); background:var(--muted); padding:2px 7px; border-radius:6px;
    font-size:12px; }}
  .hero {{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
    padding:28px 32px; margin-bottom:20px; box-shadow:var(--shadow); }}
  .verdict {{ font-size:22px; font-weight:650; letter-spacing:-.02em; margin-bottom:8px; }}
  .legend {{ color:var(--muted-foreground); font-size:13px; margin-bottom:18px; }}
  .legend b {{ font-weight:600; }}
  .legend b.wa {{ color:var(--a); }} .legend b.wb {{ color:var(--b); }}
  .winbar {{ display:flex; height:30px; border-radius:8px; overflow:hidden; font-size:12px;
    font-weight:600; color:#fff; gap:2px; background:var(--background); }}
  .winbar .seg {{ display:flex; align-items:center; justify-content:center; min-width:0; }}
  .winbar .sa {{ background:var(--a); }} .winbar .sb {{ background:var(--b); }}
  .winbar .st {{ background:var(--tie); color:var(--muted-foreground); }}
  .panel {{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
    padding:24px 26px 12px; margin-bottom:20px; box-shadow:var(--shadow); }}
  h2 {{ font-size:13px; font-weight:600; color:var(--foreground); margin:0 0 16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:right; color:var(--muted-foreground); font-weight:500; padding:0 12px 10px;
    border-bottom:1px solid var(--border); font-size:12px; }}
  th:first-child {{ text-align:left; }}
  td {{ padding:13px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
  tbody tr:last-child td {{ border-bottom:none; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:500; }}
  td.q {{ max-width:300px; font-weight:500; }}
  td.ans {{ color:var(--muted-foreground); font-size:12.5px; max-width:240px; }}
  .why {{ color:var(--muted-foreground); font-size:12.5px; font-weight:400; margin-top:4px; }}
  .win {{ font-size:11px; font-weight:600; padding:2px 9px; border-radius:6px; white-space:nowrap; color:#fff; }}
  .win.wa {{ background:var(--a); }} .win.wb {{ background:var(--b); }}
  .win.wt {{ background:var(--tie); color:var(--muted-foreground); }}
  footer {{ color:var(--muted-foreground); font-size:12.5px; text-align:center; margin-top:36px; }}
  footer a {{ color:var(--foreground); text-decoration:none; }}
  footer a:hover {{ text-decoration:underline; }}
</style></head>
<body><div class="wrap">
  <header>
    <div>
      <h1>RAG A/B — blind <span class="kit">· proofrag</span></h1>
      <div class="tagline">Blind pairwise judging across {n} cases, answers in randomized order.</div>
    </div>
    <div class="meta">judge <code class="mono">{judge}</code><br>{created} · {n} cases</div>
  </header>

  <div class="hero">
    <div class="verdict">{verdict}</div>
    <div class="legend"><b class="wa">{a}</b> {aw} · tie {tw} · <b class="wb">{b}</b> {bw}</div>
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
