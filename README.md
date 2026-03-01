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

## Run Mode Reference

| Mode | Purpose | Command example | Outputs |
|------|---------|----------------|---------|
| `DAILY_SCAN` | 24h sector snapshot | `--run-mode DAILY_SCAN --hours 24` | Sector rows → Sheets + Notion page |
| `SECTOR_RANKING` | Multi-day ranking | `--run-mode SECTOR_RANKING --hours 168` | Ranked sector rows |
| `TOKEN_SHORTLIST` | Sectors → tokens (2-pass) | `--run-mode TOKEN_SHORTLIST --discovery` | Sector + token rows; subreddit proposals |
| `CYCLE_MAP_BUILD` | Historical cycle playbook | `--run-mode CYCLE_MAP_BUILD` | Cycle evidence JSON + Notion page |

### Per-run artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| Run log | `logs/YYYYMMDD_MODE_RUNID.log` | JSON-lines log of each pipeline step |
| Pending issues | `tasks/pending_issues.jsonl` | Network failures and zero-item feeds |
| Sheets sectors tab | `sectors` | One row per sector per run |
| Sheets tokens tab | `tokens` | One row per token (TOKEN_SHORTLIST only) |
| Notion page | Database page per run | Full markdown + JSON output |

> Always use `--dry-run` first to verify pipeline without writing to Sheets/Notion.

## VS Code helpers
This repo includes:
- `.vscode/tasks.json` — one-click tasks (setup, run modes)
- `.vscode/launch.json` — debug configs

Run tasks:
- VS Code → Terminal → **Run Task…**

## Phase 2: Discovery Layer

Phase 2 adds a **non-Reddit signal layer** to `TOKEN_SHORTLIST`, improving token discovery and confidence classification.

### What `--discovery` activates

- **RSS feeds**: fetches items from 8 curated crypto research/news feeds (The Block, Messari, Bankless, Decrypt, CoinDesk, Cointelegraph, Token Terminal, The Defiant)
- **Subreddit merge**: merges `baseline_subreddits` + `discovery_subreddits` from `config.json` (deduped by name)
- **Enhanced scoring**: `token_confidence_score()` gains `discovery_count`, `fundamentals_hint`, `risk_flag` signals
- **Tier classification**: every token gets `"tier": "investment_quality"` or `"speculative"`
- **Subreddit proposals**: LLM proposes up to 3 subreddit adjustments per run (human-review only, nothing auto-applied)

### Example command

```bash
python radar_export.py --run-mode TOKEN_SHORTLIST --hours 24 --dry-run --discovery
```

### Discovery sources file

Sources are defined in `discovery_sources.json`. To add a new source:
1. Add an entry to the `sources` array with `"type": "rss"` and `"fetchable": true`
2. Sources with `"fetchable": false` are silently skipped (JS-rendered pages)

### Subreddit proposals workflow

After each `--discovery` run, the output JSON includes a `subreddit_proposals` key:
```json
{
  "notice": "HUMAN REVIEW REQUIRED — edit discovery_subreddits in config.json to apply.",
  "add":    [{"name": "HyperliquidTrading", "reason": "..."}],
  "remove": []
}
```
To apply a proposal: manually edit `discovery_subreddits` in `config.json`. Nothing is auto-written.

### Interpreting the `tier` field

| Tier | Meaning |
|------|---------|
| `investment_quality` | Token appeared in non-Reddit sources **and** confidence ≥ 50 + subreddit_spread ≥ 3; fundamentals language detected |
| `speculative` | Reddit-only signal or insufficient spread — treat as early-stage watch list |

## Git + Claude workflow (recommended)
See `ClaudeBible.md` for the daily routine (worktrees, plan mode, verify, review, cleanup).
