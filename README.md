# Crypto Sector Cycle Radar

A lightweight Python tool that:
- Pulls **Reddit RSS** posts from a configured list of crypto-related subreddits (`config.json`)
- Maintains a rolling **trend ledger** (`LEDGER_PATH`) to summarize recent activity
- Builds outputs for multiple run modes (e.g. DAILY_SCAN / SECTOR_RANKING / TOKEN_SHORTLIST / CYCLE_MAP_BUILD)
- Optionally exports to **Notion** and **Google Sheets** (credentials in `.env`)

> This repo is set up to be used with **Claude Code** + the included **project agents** under `.claude/agents/`.

## Quickstart

### 1) Create `.env` (do not commit)
Copy:
- `.env.example` → `.env`

Fill:
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `GSHEETS_SPREADSHEET_ID`
- `GSHEETS_SA_KEY` (recommended: `.secrets/gsheets_sa.json`)

### 2) Put Google service account key
Place your key file at:
- `.secrets/gsheets_sa.json`

### 3) Create venv + install deps
In Git Bash:
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -U pip
pip install -r requirements.txt
```

### 4) Run (dry-run first)
```bash
python radar_export.py --run-mode DAILY_SCAN --hours 24 --dry-run
```

## Run modes

- `DAILY_SCAN` — scan recent window (default 24h)
- `SECTOR_RANKING` — sector narrative ranking (set `--hours` for window, e.g. 168 for 7d)
- `TOKEN_SHORTLIST` — shortlist tokens (set window with `--hours`)
- `CYCLE_MAP_BUILD` — build/update historical cycle evidence from `cycle_sources.json`

Helpful flags:
- `--dry-run` prints preview instead of exporting
- `--include-memes` includes meme-like posts (default excludes)
- `--refresh-cycle-sources` forces re-fetch for cycle sources cache

## VS Code helpers
This repo includes:
- `.vscode/tasks.json` — one-click tasks (setup, run modes)
- `.vscode/launch.json` — debug configs

Run tasks:
- VS Code → Terminal → **Run Task…**

## Git + Claude workflow (recommended)
See `ClaudeBible.md` for the daily routine (worktrees, plan mode, verify, review, cleanup).
