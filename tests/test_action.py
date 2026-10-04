"""Exercise the composite Action shell without package downloads."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest


def _evaluation_script():
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text()
    return textwrap.dedent(action.split("      run: |\n", 1)[1].split("    - name:", 1)[0])


@pytest.mark.parametrize("produces_results", [False, True])
@pytest.mark.parametrize("report_failure", [False, True])
def test_action_does_not_report_or_diff_stale_results(tmp_path, produces_results, report_failure):
    uvx = tmp_path / "uvx"
    uvx.write_text(
        "#!/bin/bash\n"
        "shift 3\n"
        'echo "$1" >> "$CALLS"\n'
        'if [ "$1" = evaluate ]; then\n'
        '  while [ "$1" != --out ]; do shift; done\n'
        '  if [ "$PRODUCES_RESULTS" = true ]; then echo "fresh" > "$2"; fi\n'
        "  exit 2\n"
        "fi\n"
        'if [ "$1" = report ]; then\n'
        '  [ "$REPORT_FAILURE" = true ] && exit 2\n'
        '  while [ "$1" != --out ]; do shift; done\n'
        '  echo "fresh report" > "$2"\n'
        "fi\n"
    )
    uvx.chmod(0o755)
    results = tmp_path / "results.json"
    results.write_text("stale")
    scorecard = tmp_path / "scorecard.html"
    scorecard.write_text("stale report")
    output = tmp_path / "output"
    output.touch()
    calls = tmp_path / "calls"
    env = os.environ | {
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "CALLS": str(calls),
        "PRODUCES_RESULTS": str(produces_results).lower(),
        "REPORT_FAILURE": str(report_failure).lower(),
        "GOLDENSET": "gold.jsonl",
        "PREDICTIONS": "predictions.jsonl",
        "RESULTS": str(results),
        "SCORECARD": str(scorecard),
        "FAIL_UNDER": "",
        "BASELINE": "baseline.json",
        "TOLERANCE": "0.02",
        "K": "5",
        "SEMANTIC": "false",
        "EXACT": "false",
        "EXTRA": "",
        "VERSION": "0.9.0",
        "BACKEND": "jev",
        "MODEL": "jev-1.13.0",
        "GITHUB_OUTPUT": str(output),
    }
    run = subprocess.run(["bash", "-c", _evaluation_script()], env=env, capture_output=True)
    assert run.returncode == 2
    assert results.read_text().strip() == ("fresh" if produces_results else "stale")
    assert calls.read_text().splitlines() == (
        ["evaluate", "report", "diff"] if produces_results else ["evaluate"]
    )
    expected_outputs = ["generated=true", f"results={results}"] if produces_results else []
    if produces_results and not report_failure:
        expected_outputs.append(f"scorecard={scorecard}")
        assert scorecard.read_text().strip() == "fresh report"
    else:
        assert scorecard.read_text() == "stale report"
    assert output.read_text().splitlines() == expected_outputs
