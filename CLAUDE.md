# Project Instructions

Follow my global rules: @~/.claude/CLAUDE.md

## Project-specific notes
- Build:
- Test:
- Lint:

## Token Budget Rules (this repo)
- This repo runs in Token Budget Mode by default
- `radar_export.py` is 1635 lines — read by targeted range, never full file
- Use `SECTOR_KEYWORDS` for sector tagging before any LLM call
- Never pass full ledger to prompts — use `trim_ledger_for_prompt()` output only
