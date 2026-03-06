# Project Instructions

Follow my global rules: @~/.claude/CLAUDE.md

## Project-specific notes
- Build:
- Test:
- Lint:

## Token Budget Rules (this repo)
- This repo runs in Token Budget Mode by default.
- No broad repo scans. Start from:
  1) README.md
  2) CLAUDE.md (this file)
  3) config files (config.json, cycle_sources.json)
  4) then only the relevant functions in radar_export.py
- `radar_export.py` is large — always read by targeted range (never full file).
- Never paste full ledgers/logs into prompts:
  - use trimmed summaries only (e.g., `trim_ledger_for_prompt()` output).
- Sector tagging must be rules-first:
  - use `SECTOR_KEYWORDS` (or equivalent) to tag/filter before any LLM call.
- Spec-first workflow:
  - ChatGPT writes `docs/specs/*` and `docs/research/*`
  - Claude implements those specs.

## Model switching protocol (Claude ↔ ChatGPT)
- If Claude credits stop:
  1) Generate a handoff packet (`git status`, `git diff --stat`, relevant `git diff`, last command + error)
  2) Paste into ChatGPT using `prompts/chatgpt/HandoffHelper.md`
  3) Save output into `docs/specs/<name>.md` or `tasks/pending_issues.md`
  4) When Claude is back, resume using `prompts/claude/ResumeAfterLimit.md`

## Agents usage (preferred)
- Use `explorer` first to locate files/commands.
- Use `test-runner` to run checks and summarize results.
- Use `debugger` when failures occur.
- Use `code-reviewer` before PR/merge or before declaring done.