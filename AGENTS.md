# Agents

This repo ships **proofrag** as a portable [Agent Skill](https://agentskills.io):
`skills/proofrag/SKILL.md`. The skill is the interface; the `proofrag` Python CLI
(`src/proofrag/`) is the engine it drives.

## Use it as a skill

**Claude Code (plugin):**
```
/plugin marketplace add unshDee/proofrag
/plugin install proofrag@proofrag
```
Then just ask: *"evaluate my RAG"* — Claude auto-loads the skill. Or type `/proofrag`.

**Claude Code (manual):** copy the skill folder where Claude discovers skills:
```
cp -r skills/proofrag ~/.claude/skills/        # personal
cp -r skills/proofrag .claude/skills/          # this project only
```

**Codex / other agents (open standard):** drop the skill into your agent's skills
directory (e.g. `.agents/skills/` or your tool's equivalent):
```
cp -r skills/proofrag .agents/skills/
```

## Install the engine

The skill calls the `proofrag` CLI. Install it once, or run ad-hoc with `uvx`:
```
uv tool install "proofrag[anthropic]"     # or: pipx install "proofrag[anthropic]"
uvx "proofrag[anthropic]" demo            # no install
```
Set `ANTHROPIC_API_KEY` (default Haiku) or `OPENAI_API_KEY` (`OPENAI_BASE_URL` for
local/Ollama). No key needed for `proofrag demo`.
