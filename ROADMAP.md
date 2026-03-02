# Roadmap

## Phase 1 — Complete

- File logging + pending_issues writer
- fetch_with_retry (3 attempts, Retry-After backoff)
- Dead RSS feeds fixed; per-run in-memory cache
- config.json restructured (core / baseline / discovery / exclude pools)
- SECTOR_KEYWORDS pre-filter + filter_no_sector() (drops off-taxonomy posts)
- Token confidence scoring (multi-signal: mentions, spread, engagement, discovery)
- Sheets + Notion schema expansion
- Schema compliance fix (num_ctx=16384, selftext_max=400, _SCHEMA_REMINDER)

## Phase 2 — Complete

- [x] Discovery RSS layer (--discovery flag, 6 fetchable sources)
- [x] Tier classification (investment_quality / speculative)
- [x] Subreddit proposals (LLM suggests, human applies)
- [x] Cycle evidence local artifact (data/cycle_summary_latest.json)
- [x] Token tracking registry (config.json token_tracking wired)
- [x] Discovery source health monitoring (auto-flag dead feeds)
- [x] Google Sheets schema alignment (ensure_sheet_headers)

## Phase 3 — Planned

- Upgrade Ollama model (llama3.1:8b → larger or fine-tuned)
- StarknetCrypto: investigate consistently-zero RSS (may need replacement)
- Multi-day trend scoring (ledger diff across runs)
- Scheduled runs (cron/Task Scheduler integration)
