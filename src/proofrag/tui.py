"""`proofrag wizard`: a guided, interactive run of the whole evaluation loop.

Needs the optional extra: pip install "proofrag[tui]" (rich + typer). Every step
calls the same functions as the plain CLI commands, so the artifacts are identical.

Live regions stay one line tall on purpose. A rich Live display taller than the
terminal can't redraw in place and reprints itself on every refresh, so tables and
panels are only ever printed after the progress bars finish.
"""

from __future__ import annotations

import logging
import sys
import time
import webbrowser
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.progress_bar import ProgressBar
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from .corpus import corpus_stats, load_corpus
from .goldenset import generate, read_jsonl, write_jsonl
from .judge import evaluate, write_results
from .llm import LLM, LLMError
from .metrics import RETRIEVAL_METRICS
from .run import RunError, callable_runner, endpoint_runner, run_predictions, write_predictions
from .scorecard import _gen_label, _gen_metrics, _ret_labels, case_mean, headline, write_html
from .validate import validate_goldenset

console = Console()
app = typer.Typer(add_completion=False, help="Guided, interactive proofrag run.")
STEPS = ("Your docs", "Golden set", "Your RAG app", "Evaluate")


class _CountingLLM(LLM):
    """Ticks a progress bar after each call. Generation and judging make one per case."""

    def __init__(self, tick: Callable[[], None]):
        super().__init__()
        self._tick = tick

    def complete_json(self, system: str, prompt: str):
        try:
            return super().complete_json(system, prompt)
        finally:
            self._tick()


@contextmanager
def _bar(label: str, total: int) -> Iterator[Callable[[], None]]:
    """A one-line progress bar; yields the function that advances it.

    rich redirects sys.stdout/stderr while the bar is live, so the user's app prints
    land above it. Logging handlers configured earlier still hold the real streams and
    would write under the cursor, leaving a stale copy of the bar per log line, so
    they are pointed at the redirected streams until the bar finishes.
    """
    real = {id(sys.stdout): "stdout", id(sys.stderr): "stderr"}
    progress = Progress(
        SpinnerColumn("dots", style="cyan"),
        TextColumn("{task.description}"),
        BarColumn(bar_width=30, complete_style="cyan", finished_style="green"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        moved = [(h, h.stream) for h in _stream_handlers() if id(h.stream) in real]
        for h, stream in moved:
            h.setStream(getattr(sys, real[id(stream)]))
        try:
            task = progress.add_task(label, total=total)
            yield lambda: progress.advance(task)
        finally:
            for h, stream in moved:
                h.setStream(stream)


def _stream_handlers() -> list[logging.StreamHandler]:
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    return [
        h
        for lg in loggers
        if isinstance(lg, logging.Logger)
        for h in lg.handlers
        if isinstance(h, logging.StreamHandler)
    ]


def _step(i: int, title: str) -> None:
    dots = "".join("●" if j <= i else "○" for j in range(1, len(STEPS) + 1))
    console.print()
    console.rule(
        f"[cyan]{dots}[/]  [bold]Step {i} of {len(STEPS)}[/] · {title}",
        align="left",
        style="grey37",
    )


def _done(message: str) -> None:
    console.print(f"  [green]✓[/] {message}")


def _ask_int(question: str, default: int) -> int:
    while (value := IntPrompt.ask(question, default=default, console=console)) < 1:
        console.print("  [red]Enter a number above zero.[/]")
    return value


@app.command()
def wizard(
    corpus: Annotated[Path | None, typer.Option(help="Docs folder (asked if omitted).")] = None,
    cases: Annotated[int | None, typer.Option(min=1, help="Golden cases to generate.")] = None,
    k: Annotated[int, typer.Option(min=1, help="Retrieval cutoff for Recall@k, NDCG@k.")] = 5,
    out_dir: Annotated[Path, typer.Option(help="Where to write the artifacts.")] = Path("."),
) -> None:
    """Build a golden set from your docs, run your RAG app, and score it."""
    try:
        _run(corpus, cases, k, out_dir)
    except (LLMError, RunError, OSError, ValueError) as e:
        console.print(Panel(str(e), title="error", title_align="left", border_style="red"))
        raise typer.Exit(2) from e
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelled.[/]")
        raise typer.Exit(130) from None


def _run(corpus: Path | None, cases: int | None, k: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    gold_path = out_dir / "goldenset.jsonl"
    pred_path = out_dir / "predictions.jsonl"
    results_path = out_dir / "results.json"
    html_path = out_dir / "scorecard.html"

    console.print(
        Panel.fit(
            "[bold]proofrag[/] [dim]wizard[/]\n"
            "[dim]Build a golden set from your docs, run your RAG app, and score it.\n"
            "Press Ctrl+C to quit at any time.[/]",
            border_style="cyan",
            padding=(1, 3),
        )
    )

    _step(1, STEPS[0])
    while corpus is None or not corpus.exists():
        if corpus is not None:
            console.print(f"  [red]✗[/] {corpus} does not exist")
        default = "docs" if Path("docs").is_dir() else "."
        corpus = Path(Prompt.ask("  Docs folder", default=default, console=console))
    with console.status("  Reading and chunking…", spinner="dots"):
        chunks = load_corpus(str(corpus))
    if not chunks:
        raise ValueError(f"no readable docs found in {corpus}")
    stats = corpus_stats(chunks)
    _done(f"Loaded [bold]{stats['chunks']}[/] chunks from {stats['sources']} files in {corpus}")

    _step(2, STEPS[1])
    reuse = gold_path.exists() and (
        Confirm.ask(f"  Reuse existing [bold]{gold_path}[/]?", default=True, console=console)
        or not Confirm.ask(
            f"  Overwrite {gold_path}? Any manual review in it is lost",
            default=False,
            console=console,
        )
    )
    if reuse:
        golden = read_jsonl(str(gold_path))
    else:
        n = cases or _ask_int("  How many test cases?", 10)
        with _bar("Writing questions", n) as tick:
            golden = generate(chunks, n=n, llm=_CountingLLM(tick))
        write_jsonl(golden, str(gold_path))
    tiers = Counter(str(r.get("difficulty", "")) for r in golden)
    mix = ", ".join(f"{v} {name}" for name, v in tiers.items())
    _done(f"{len(golden)} cases → {gold_path}  [dim]({mix})[/]")
    report = validate_goldenset(str(gold_path), corpus=str(corpus))
    if report["errors"]:
        raise ValueError(
            f"golden set has {len(report['errors'])} error(s); "
            f"see `proofrag validate --goldenset {gold_path}`"
        )
    _done(f"Validated  [dim]({len(report['warnings'])} warnings)[/]")

    _step(3, STEPS[2])
    console.print(
        "  How should proofrag call your app?\n"
        "    [cyan]callable[/]  a Python function, as module:function\n"
        "    [cyan]endpoint[/]  an HTTP endpoint that accepts {id, question}\n"
        "    [cyan]file[/]      a predictions.jsonl you already have",
        highlight=False,
    )
    how = Prompt.ask(
        "  Choose", choices=["callable", "endpoint", "file"], default="callable", console=console
    )
    run_cmd = None
    if how == "file":
        pred_path = Path(Prompt.ask("  Predictions file", default=str(pred_path), console=console))
        predictions = read_jsonl(str(pred_path))
    else:
        label = "  Function (module:function)" if how == "callable" else "  Endpoint URL"
        target = Prompt.ask(label, console=console)
        runner = callable_runner(target) if how == "callable" else endpoint_runner(target)
        with _bar("Asking your app", len(golden)) as tick:

            def run(record):
                try:
                    return runner(record)
                finally:
                    tick()

            predictions = run_predictions(golden, run)
        write_predictions(predictions, str(pred_path))
        run_cmd = f"proofrag run --goldenset {gold_path} --{how} {target} --out {pred_path}"
    _done(f"{len(predictions)} answers → {pred_path}")

    _step(4, STEPS[3])
    with _bar("Judging answers", len(golden)) as tick:
        results = evaluate(golden, predictions, llm=_CountingLLM(tick), k=k)
    write_results(results, str(results_path))
    write_html(results, str(html_path))
    _show_results(results)

    files = Table.grid(padding=(0, 2))
    for name, path in [
        ("golden set", gold_path),
        ("predictions", pred_path),
        ("results", results_path),
        ("scorecard", html_path),
    ]:
        files.add_row(f"[dim]{name}[/]", str(path))
    console.print(Panel(files, title="Files", title_align="left", border_style="grey37"))
    console.print("  [dim]Re-run without the wizard, e.g. in CI:[/]")
    for cmd in filter(
        None,
        [
            run_cmd,
            f"proofrag evaluate --goldenset {gold_path} --predictions {pred_path} --k {k}",
            f"proofrag report --results {results_path} --out {html_path}",
        ],
    ):
        console.print(f"  [cyan]$[/] {cmd}", soft_wrap=True)
    console.print()
    if Confirm.ask("  Open the scorecard in your browser?", default=True, console=console):
        webbrowser.open(html_path.resolve().as_uri())


def _show_results(results: dict) -> None:
    overall, verdict = headline(results)
    color = "red" if overall < 65 else "yellow" if overall < 85 else "green"
    console.print()
    # Count-up: a transient single line, so the redraw can never outgrow the screen.
    with Live(console=console, transient=True, refresh_per_second=60) as live:
        for v in range(0, overall + 1, max(1, overall // 25)):
            live.update(Text(f"  {v}", style=f"bold {color}"))
            time.sleep(0.02)

    gen = _gen_metrics(results)
    agg = results.get("aggregate", {})
    labels = {d: _gen_label(d) for d in gen} | _ret_labels(results.get("k", 5))
    metrics = Table.grid(padding=(0, 2))
    for section, names in (("Generation", gen), ("Retrieval", RETRIEVAL_METRICS)):
        metrics.add_row(f"[dim]{section}[/]", "", "")
        for name in names:
            pct = round(agg.get(name, 0.0) * 100)
            style = "red" if pct < 65 else "white"
            metrics.add_row(
                f"  {labels[name]}",
                # finished_style too, or rich paints a full (100) bar green
                ProgressBar(
                    total=100, completed=pct, width=24, complete_style=style, finished_style=style
                ),
                f"[{style}]{pct:>3}[/]",
            )

    body = Table.grid()
    body.add_row(Text.assemble((f"{overall}", f"bold {color}"), ("/100   ", "dim"), verdict))
    body.add_row("")
    body.add_row(metrics)
    ranked = sorted(results.get("records", []), key=lambda r: case_mean(r, gen))
    worst = [r for r in ranked if case_mean(r, gen) < 0.65][:3]
    if worst:
        body.add_row("")
        body.add_row("[dim]Needs attention[/]")
        for r in worst:
            body.add_row(
                Text.assemble(
                    ("  ✗ ", "red"),
                    (f"{round(case_mean(r, gen) * 100):>3}  ", "red"),
                    str(r.get("question", "")),
                    overflow="ellipsis",
                    no_wrap=True,
                )
            )
    console.print(Panel(body, title="Results", title_align="left", border_style="cyan"))
    if results.get("evaluation_errors"):
        console.print(
            f"  [red]Invalid run:[/] {len(results['evaluation_errors'])} judge calls failed. "
            "Rerun before trusting these scores."
        )
