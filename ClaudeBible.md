# Claude Bible — Crypto Sector Cycle Radar

This is the daily workflow for this project, tuned for:
- **VS Code + Git Bash**
- **Claude Code**
- **Worktrees (one task = one branch)**
- **Evidence-based verification**

Repo (recommended name): `crypto-sector-cycle-radar`  
Recommended local path example: `C:\Users\user\Desktop\Bruno\Data Projects\Repo\crypto-sector-cycle-radar`

---

## A) Start-of-day (PC on → ready)

1) Open VS Code → open folder `C:\Users\user\Desktop\Bruno\Data Projects\Repo\crypto-sector-cycle-radar` (or your actual path).
2) Terminal → New Terminal → **Git Bash**
3) Quick sanity:
```bash
which git
which claude
claude --version
```

---

## B) If this is a NEW clone / new machine

### 1) Create `.env` (do not commit)
Copy:
- `.env.example` → `.env`

Fill the required values:
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `GSHEETS_SPREADSHEET_ID`
- `GSHEETS_SA_KEY=.secrets/gsheets_sa.json`

### 2) Place secrets
- Put Google service account JSON at `.secrets/gsheets_sa.json`
- Confirm `.secrets/` and `.env` are ignored (see `.gitignore.append`)

### 3) Setup venv
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -U pip
pip install -r requirements.txt
```

---

## C) Every day: start working

### 1) Verify repo root
```bash
pwd
git rev-parse --show-toplevel
git status
```

### 2) Sync
```bash
git fetch --all
git pull --rebase
```

### 3) Activate venv (if using Python)
```bash
source .venv/Scripts/activate
python --version
```

### 4) Use worktrees (one task = one folder)
```bash
git worktree list
```

Create a new task worktree:
```bash
cd "$(git rev-parse --show-toplevel)"
git worktree add .claude/worktrees/<task> -b <branch>
cd ".claude/worktrees/<task>"
```

---

## D) During work: the screenshot workflow (use this loop)

### 1) Plan Mode first
Run Claude:
```bash
claude
```
Say:
> “Plan mode: write a step-by-step plan first, then wait.”

If confusion happens:
> “Stop. Switch back to plan mode. Re-plan with the new info.”

### 2) Use project agents (fast + clean)
List them:
- In Claude: `/agents`
- Or terminal: `claude agents`

Recommended usage:
- **explorer**: map repo + find build/test/run commands
- **test-runner**: run tests/linters and summarize
- **debugger**: repro → isolate → minimal fix plan → verify
- **code-reviewer**: strict diff review vs main

### 3) Verify before “done”
Use:
- `/verify` (prove it works)

### 4) Commit small, push often
```bash
git status
git diff
git add -A
git commit -m "..."
git push
```

### 5) Dry-run first for safety
Always start with `--dry-run`:
```bash
python radar_export.py --run-mode DAILY_SCAN --hours 24 --dry-run
```

Then run without `--dry-run` when ready (exports enabled).

---

## E) End-of-day (finish clean)

1) Ensure no accidental changes left:
```bash
git status
```

2) Update tracking:
- `tasks/todo.md`
- `tasks/lessons.md`

3) Push what matters (or stash if mid-flight):
```bash
git push
# or
git stash -u
```

---

## F) Useful next upgrades (optional)
- Add CI checks (run a dry-run mode in PR)
- Add Makefile (`make setup`, `make run`)
- Configure Claude statusline (`/statusline`)
