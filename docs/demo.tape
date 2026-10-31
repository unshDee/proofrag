# Render with:  vhs docs/demo.tape   (from the repo root; needs an API key in .env
# and `uv sync --extra tui`). Runs the wizard on a fresh copy of examples/docs-rag.
Output docs/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 820
Set Padding 24
Set Margin 24
Set MarginFill "#2563eb"
Set WindowBar Colorful
Set BorderRadius 10
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms
Set WaitTimeout 90s

Hide
Type "export PATH=$PWD/.venv/bin:$PATH && set -a && source .env && set +a" Enter
Type "D=$(mktemp -d)/docs-bot && cp -r examples/docs-rag $D && rm -rf $D/__pycache__ && cd $D" Enter
Type "export PS1='\[\e[38;5;111m\]docs-bot\[\e[0m\] $ ' && clear" Enter
Sleep 1s
Show

Type "ls" Sleep 300ms Enter
Sleep 800ms
Type "proofrag wizard" Sleep 400ms Enter

Wait+Screen /Docs folder/
Sleep 700ms
Type "corpus" Sleep 300ms Enter

Wait+Screen /How many test cases/
Sleep 600ms
Type "6" Sleep 300ms Enter

Wait+Screen /Choose/
Sleep 1200ms
Type "callable" Sleep 300ms Enter
Wait+Screen /Function/
Sleep 400ms
Type "naive_rag:ask" Sleep 400ms Enter

Wait /Open the scorecard/
Sleep 4s
Type "n" Enter
Sleep 2s
