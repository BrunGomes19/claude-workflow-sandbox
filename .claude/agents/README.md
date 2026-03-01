# Project Subagents (v3)

Drop `.claude/agents/` into your repo root and commit.

Verify:
- `ls -la .claude/agents`
- In Claude Code: `/agents`
- In terminal: `claude agents`

Suggested daily flow:
1) Use `explorer` to map repo + find run commands
2) Use main Claude session to implement changes
3) Use `test-runner` to execute checks
4) Use `debugger` when failures occur (repro -> isolate -> fix plan)
5) Use `code-reviewer` before PR/merge

Tip: Keep agents mostly **read-only** (no Write/Edit tools) to reduce churn.
