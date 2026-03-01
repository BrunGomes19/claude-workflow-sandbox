# Claude Bible (for this repo)

This document is my **“how I work” playbook** for this project: it helps me restart fast, stay consistent, and avoid breaking things.

Repo path (Windows): `C:\Users\user\Desktop\Bruno\Data Projects\Repo\claude-workflow-sandbox`  
Shell: **Git Bash** inside VS Code (recommended)

---

## 1) Every time I come back to this project and want to work

### 1.1 Open the project the safe way
1) Open **VS Code**  
2) **File → Open Folder…**  
3) Select:  
   `C:\Users\user\Desktop\Bruno\Data Projects\Repo\claude-workflow-sandbox`  
4) Open **Git Bash** terminal: **Terminal → New Terminal → Git Bash**

### 1.2 Verify you’re in the correct folder (do this every time)
In Git Bash:

```bash
pwd
git rev-parse --show-toplevel
```

✅ Good if both point to the same repo folder.

### 1.3 Sync with GitHub (so you don’t work on old code)
```bash
git status
git fetch --all
git pull --rebase
```

If `git pull --rebase` complains about local changes:
- Either commit your changes, or
- stash them:
```bash
git stash -u
git pull --rebase
git stash pop
```

### 1.4 Choose where to work (main vs worktrees)
**Rule:** *One task = one folder (worktree) = one branch.*

Check worktrees:
```bash
git worktree list
```

Go to a worktree (examples):
```bash
cd ".claude/worktrees/feat-1"
# or
cd ".claude/worktrees/analysis"
```

If you’re doing a brand-new task, create a fresh worktree (recommended):
```bash
cd "/c/Users/user/Desktop/Bruno/Data Projects/Repo/claude-workflow-sandbox"
git worktree add .claude/worktrees/<task-name> -b <branch-name>
```
Example:
```bash
git worktree add .claude/worktrees/feat-login -b feat/login
```

### 1.5 Python `.venv` setup (only if this repo uses Python)
#### First time (create venv)
From the **repo root** (or inside a worktree — both work):
```bash
python --version
python -m venv .venv
```

#### Every time (activate venv)
In Git Bash:
```bash
source .venv/Scripts/activate
```

✅ Confirm it’s active:
```bash
which python
python --version
```

#### Install dependencies
If there is `requirements.txt`:
```bash
pip install -r requirements.txt
```
If there is `pyproject.toml` and you use pip:
```bash
pip install -U pip
pip install .
```

#### VS Code interpreter (recommended)
1) `Ctrl+Shift+P` → **Python: Select Interpreter**  
2) Choose the interpreter inside `.venv`

### 1.6 “Baby Git” workflow (micro-steps)
#### A) Before you change anything
```bash
git status
git branch --show-current
```

#### B) Make changes (edit code)
Use VS Code.

#### C) See what changed
```bash
git diff
git status
```

#### D) Stage changes
```bash
git add -A
```

#### E) Commit
```bash
git commit -m "Short, clear message of what I changed"
```

#### F) Push
```bash
git push
```

#### G) (Recommended) Use Pull Requests for anything non-trivial
On GitHub:
- **Pull requests → New pull request**
- base: `main`
- compare: your branch (`feat/...`, `fix/...`, etc.)
- merge after review

### 1.7 End-of-session checklist (2 minutes)
1) Make sure you didn’t forget a worktree folder open on the wrong branch:
```bash
git status
```

2) Update your task tracking:
- `tasks/todo.md` → what’s next
- `tasks/lessons.md` → one line if you learned something

3) Push your work (or stash if you’re mid-flight):
```bash
git push
# or
git stash -u
```

---

## 2) The screenshot workflow (synthesized) + how to use it daily

### 2.1 What the workflow concepts mean (simple language)

#### A) **Plan Mode** (stop Claude from rushing)
- Before Claude edits files, you force it to write a plan first.
- This prevents “random changes” and makes work predictable.

What you say to Claude:
> “Plan mode: write a step-by-step plan first, then wait.”

Use Plan Mode when:
- task has 3+ steps
- touches multiple files
- any risk (deploy, auth, money, data loss)

#### B) **Parallel work with worktrees** (no task-mixing)
- Different tasks live in different folders and branches.
- You can run multiple Claude sessions in parallel without conflicts.

Typical layout:
- `.claude/worktrees/feat-1` → feature work  
- `.claude/worktrees/analysis` → explore logs / read code / experiments  
- (recommended) `.claude/worktrees/bug-1` → bugfix only

#### C) **Verification before done** (always prove)
- Never trust “it should work”.
- You run checks/tests and show evidence.

This is what `/verify` is for.

#### D) **Demand elegance** (but don’t over-engineer)
- If a solution looks hacky, stop and ask for a cleaner design.
- Still keep it simple (avoid unnecessary complexity).

#### E) **Self-improvement loop** (teach Claude your rules)
- When Claude makes a mistake and you correct it:
  - add a short rule so it doesn’t happen again
  - keep rules in `~/.claude/CLAUDE.md` (global) and/or repo `CLAUDE.md` (project)

Copy-paste phrase:
> “Add a short rule to CLAUDE.md to prevent this mistake again. Show me the exact text.”

#### F) **Skills** (your “quality buttons”)
You already have global skills:
- `/verify` → prove it works
- `/review-me` → strict reviewer before PR
- `/techdebt` → cleanup at end of session

Use them like this:
- before saying “done” → `/verify`
- before PR/merge → `/review-me`
- end of session → `/techdebt`

#### G) **Statusline** (don’t lose track)
- Shows things like branch + context usage.
- Helps avoid “oops I was on main” and helps manage long sessions.

#### H) **Subagents** (optional but powerful)
- Create helpers (Explore / Reviewer / Test).
- They keep your main conversation focused and clean.

Command inside Claude Code:
- `/agents`

#### I) “Claude fixes bugs” workflow
When something fails, give Claude:
1) command you ran  
2) full error output  
3) file paths involved  

Then say:
> “Fix it. Don’t ask questions unless blocked. Then verify.”

### 2.2 Daily usage: step-by-step routine (copy/paste friendly)

#### Step 1 — Pick the task
Write 1 sentence: what you want done.

#### Step 2 — Choose or create a worktree
```bash
git worktree list
# if needed:
git worktree add .claude/worktrees/<task> -b <branch>
cd ".claude/worktrees/<task>"
```

#### Step 3 — Start Claude in that worktree
```bash
claude
```

#### Step 4 — Start with a plan
Tell Claude:
> “Plan mode: write a step-by-step plan first, then wait.”

#### Step 5 — Implement in small chunks
- 1 change at a time
- keep commits small

#### Step 6 — Verify
Inside Claude:
- `/verify`  
Or run your test command(s) manually and paste output.

#### Step 7 — Commit + push
```bash
git status
git add -A
git commit -m "…"
git push
```

#### Step 8 — PR (if needed) + review mode
Inside Claude:
- `/review-me`

Then open PR on GitHub.

#### Step 9 — End session cleanup
Inside Claude:
- `/techdebt`  
Then update `tasks/todo.md` and `tasks/lessons.md`.

---

## 3) Useful stuff to still implement on Claude (recommended upgrades)

### 3.1 Add a dedicated bugfix worktree (recommended)
```bash
cd "/c/Users/user/Desktop/Bruno/Data Projects/Repo/claude-workflow-sandbox"
git worktree add .claude/worktrees/bug-1 -b fix/bug-1
git worktree list
```

### 3.2 Configure Claude statusline (recommended)
Inside Claude Code:
- run `/statusline`
- show at least:
  - current git branch
  - context usage %

### 3.3 Create subagents (optional)
Inside Claude Code:
- run `/agents`
Create:
- Explore Agent (find files, map codebase)
- Reviewer Agent (review diffs, spot bugs)
- Test Agent (run tests, interpret failures)

### 3.4 Make the repo portable for other machines/users (optional)
Right now your rules/skills are global (`~/.claude/...`) which is perfect for you.
If you want the repo itself to “carry the workflow”:
- add `.claude/skills/*` **inside the repo** and commit it
- expand repo `CLAUDE.md` with full operating rules (not only “import global rules”)

### 3.5 Add “one command” scripts (optional but great)
Add a `Makefile` or scripts:
- `make setup` (create venv + install deps)
- `make test`
- `make lint`
This makes verification and onboarding much easier.

### 3.6 Add guardrails (optional)
- Pre-commit hooks (formatting/lint)
- GitHub Actions CI (run tests on PR)
- PR template / checklist (forces `/verify` + evidence)

---

### Quick “where am I?” commands (use anytime)
```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
git status
git worktree list
```
