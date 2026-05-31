# Agents

This repo ships **ragproof** as a portable [Agent Skill](https://agentskills.io):
`skills/ragproof/SKILL.md`. The skill is the interface; the `ragproof` Python CLI
(`src/ragproof/`) is the engine it drives.

## Use it as a skill

**Claude Code (plugin):**
```
/plugin marketplace add unshDee/ragproof
/plugin install ragproof@ragproof
```
Then just ask: *"evaluate my RAG"* — Claude auto-loads the skill. Or type `/ragproof`.

**Claude Code (manual):** copy the skill folder where Claude discovers skills:
```
cp -r skills/ragproof ~/.claude/skills/        # personal
cp -r skills/ragproof .claude/skills/          # this project only
```

**Codex / other agents (open standard):** drop the skill into your agent's skills
directory (e.g. `.agents/skills/` or your tool's equivalent):
```
cp -r skills/ragproof .agents/skills/
```

## Install the engine

The skill calls the `ragproof` CLI. Install it once, or run ad-hoc with `uvx`:
```
uv tool install "ragproof[anthropic]"     # or: pipx install "ragproof[anthropic]"
uvx "ragproof[anthropic]" demo            # no install
```
Set `ANTHROPIC_API_KEY` (default Haiku) or `OPENAI_API_KEY` (`OPENAI_BASE_URL` for
local/Ollama). No key needed for `ragproof demo`.
