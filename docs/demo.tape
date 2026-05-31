# Render with:  vhs docs/demo.tape   (needs an API key in .env)
Output docs/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 760
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 32ms
Set PlaybackSpeed 1.4

Hide
Type "cd /Users/ansh/Documents/projects/rag-eval-kit" Enter
Type "export VIRTUAL_ENV_DISABLE_PROMPT=1 && source .venv/bin/activate" Enter
Type "export PS1='$ '" Enter
Type "set -a && source .env && set +a && clear" Enter
Sleep 1s
Show

Type "# 1. generate a golden eval set from YOUR docs" Sleep 400ms Enter
Sleep 400ms
Type "proofrag generate --corpus examples/docs-rag/corpus --n 6 --chunk-chars 400 --out goldenset.jsonl" Sleep 400ms Enter
Sleep 8s

Type "# 2. run your RAG over each question -> predictions.jsonl" Sleep 400ms Enter
Sleep 300ms
Type "python examples/docs-rag/naive_rag.py --goldenset goldenset.jsonl --corpus examples/docs-rag/corpus --out predictions.jsonl --k 3" Sleep 300ms Enter
Sleep 8s

Type "# 3. judge generation + score retrieval (pinned judge, CI gate)" Sleep 400ms Enter
Sleep 300ms
Type "proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --k 3 --fail-under 0.6" Sleep 400ms Enter
Sleep 9s

Type "# 4. shareable HTML scorecard" Sleep 400ms Enter
Sleep 300ms
Type "proofrag report --results results.json --out scorecard.html" Sleep 400ms Enter
Sleep 3s
