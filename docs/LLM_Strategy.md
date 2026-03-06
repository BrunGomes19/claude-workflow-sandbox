# LLM Strategy — Claude + ChatGPT in one repo (token-saving playbook)

Goal: keep **Claude** as the main coding engine (edits/tests), and use **ChatGPT** as a backup/sidekick for tasks that *don’t need deep repo execution*, so you **spend fewer Claude credits**.

This fits your current repo approach:
- `ClaudeBible.md` (daily workflow)
- `.claude/agents/*` (explorer / test-runner / debugger / code-reviewer)
- skills (`/verify`, `/review-me`, `/techdebt`)
- “Plan first → implement → verify” discipline

---

## 1) Golden rules (keeps tokens low)

### Rule 1 — Claude gets *only* what it needs to change code
When working with Claude, default to:
- **git diff** + 1–2 relevant files
- avoid “scan the whole repo” requests
- ask for **plan first**, then approve

### Rule 2 — ChatGPT is your “spec writer” and “doc/research helper”
Use ChatGPT to produce:
- the **spec**
- acceptance criteria
- edge cases
- documentation text
- structured research lists
Then Claude implements.

### Rule 3 — Save everything important into repo files
So you don’t repeat work when credits end:
- `tasks/pending_issues.md`
- `tasks/decision_log.md`
- `docs/specs/<feature>.md`
- `docs/research/<topic>.md`

---

## 2) Routing rules (who does what)

### Use Claude for (default)
- editing files across the repo
- running commands/tests
- debugging with stack traces
- refactoring
- anything that needs repo context + execution
- final “merge readiness” checks (with your agents)

### Use ChatGPT for (default)
- writing a **clear spec** and acceptance tests
- brainstorming alternatives
- summarizing long docs/logs you paste
- drafting Notion/Sheets schema tables
- writing README / docs / checklists
- “what-if” design discussions
- creating prompt templates and workflows

### Rule of thumb
If the task requires: **read many files + change code + run commands** → Claude.  
If the task requires: **thinking, writing, structuring** → ChatGPT.

---

## 3) The 2-phase workflow (repeatable)

### Phase A — Spec & decisions (ChatGPT)
**Objective:** produce a “ready-to-build” spec in ≤ 1–2 pages.

Output goes into:
- `docs/specs/<feature>.md`
- plus `tasks/decision_log.md` updates

ChatGPT prompt (copy/paste):
> You are my “Spec Writer”.  
> Create a concise spec for this change.  
> Include: scope, non-goals, data model/schema, algorithm steps, acceptance criteria, risks, and verification commands.  
> Keep it concrete and implementation-ready (no fluff).

### Phase B — Build & verify (Claude)
**Objective:** implement the spec with minimal changes + evidence.

Claude prompt (copy/paste):
> Plan mode + Token Budget Mode. Implement `docs/specs/<feature>.md`.  
> Constraints: minimal changes, no broad scans, ask before running risky commands.  
> After implementing: run test-runner, then /verify with evidence.  
> Before PR/merge: run code-reviewer checklist.

---

## 4) The “handoff packet” (switch models without losing context)

When Claude runs out of credits, copy/paste this packet into ChatGPT (or back into Claude later):

### Handoff template
**Goal:**  
**Branch/worktree:**  
**What changed already:**  
**What’s failing / blocked:**  

**Evidence**
```text
git status:
<PASTE>

git diff --stat:
<PASTE>

git diff (only relevant files):
<PASTE>

command + full error output:
<PASTE>
```

Minimal commands to generate evidence (Git Bash):
```bash
git status
git diff --stat
git diff
```

---

## 5) How to save Claude tokens (practical tactics)

### A) Default “Token Budget Mode” opener
Use this exact opener with Claude:
> Token Budget Mode. Do not scan the whole repo.  
> Start by reading only: README.md, CLAUDE.md, and the files I mention.  
> Provide a plan first. Keep answers short.

### B) Ask for *file lists* before reading big files
Instead of “read radar_export.py”, say:
> Show the relevant functions/sections and line ranges first. Then read only those sections.

### C) Prefer subagents instead of long main-chat reasoning
- **explorer**: map repo + locate entry points (fast, read-only)
- **test-runner**: runs checks and summarizes results
- **debugger**: isolates failure and proposes minimal fix plan
- **code-reviewer**: produces a short fix checklist

### D) Keep long research off Claude
Do research/source curation in ChatGPT → save to `docs/research/*.md` → Claude only implements.

---

## 6) Repo additions (so this becomes “one system”)

Create:
- `docs/specs/` (ChatGPT outputs implementation specs)
- `docs/research/` (ChatGPT outputs research packs)
- `tasks/pending_issues.md` (unresolved issues list)
- `tasks/decision_log.md` (short “why we decided X”)
- `docs/LLM_Strategy.md` (this file)

Optional:
- `prompts/chatgpt/SpecWriter.md`
- `prompts/chatgpt/Researcher.md`
- `prompts/claude/ImplementSpec.md`

---

## 7) Daily routine (short)

### Morning
1) Pull latest
2) Decide today’s task
3) ChatGPT → create/update `docs/specs/<task>.md`

### During work
4) Claude → implement spec in a worktree/branch
5) test-runner → run checks
6) debugger → fix failures
7) /verify → prove it works
8) code-reviewer → final checklist

### End of day
9) Update `tasks/pending_issues.md`
10) Commit + push

---

## 8) Ready-to-copy prompts

### ChatGPT: Spec Writer
> Write a spec for this change with: scope, non-goals, architecture, data model, algorithm steps, acceptance criteria, verification commands, risks.  
> Keep it implementation-ready and short.

### ChatGPT: Research Pack
> Produce a structured research pack: categories, candidate sources, quality rating, key takeaways, and how to encode it into our JSON schema.

### Claude: Implement Spec (token budget)
> Token Budget Mode + Plan mode.  
> Implement `docs/specs/<name>.md`.  
> Only read necessary files. Ask before risky commands.  
> Then run test-runner and /verify with evidence.

### Claude: Finish checklist
> Use code-reviewer on diff vs main and output a BLOCKER/MAJOR/MINOR checklist. Then /verify again.
