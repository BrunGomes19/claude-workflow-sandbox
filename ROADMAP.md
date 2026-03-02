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

## Phase 3 — Hardening & Infrastructure

Fix known bugs and make the pipeline reliable enough to run unattended.

- [ ] Fix TOKEN_SHORTLIST 2-pass crash (`clamp_scores` fails when model returns strings in `sectors` instead of dicts)
- [ ] Upgrade Ollama model (llama3.1:8b → larger or fine-tuned) — current model produces repeated narratives and low-specificity outputs
- [ ] Messari RSS: investigate `fetch_with_retry: unreachable` failure — may need `fetchable: false` like The Block
- [ ] StarknetCrypto: investigate consistently-zero RSS entries (dead feed or replacement needed)
- [ ] Revisit `discovery_limit` default (currently 5 out of ~100 fetched items — very aggressive cap)
- [ ] Multi-day trend scoring (ledger diff across runs — detect rising/falling sectors over time)
- [ ] Scheduled runs (cron or Task Scheduler, lays groundwork for Phase 6 containerisation)

## Phase 4 — Token Price Intelligence

Track discovered tokens over time and identify actionable entry and exit points.

- [ ] Price history fetcher: pull OHLCV data for tokens in `token_tracking` registry (CoinGecko or similar free API)
- [ ] Active token watchlist: a dedicated section of the pipeline for tokens we've shortlisted and want to monitor continuously — separate from the discovery ledger
- [ ] Entry/exit signal detection: rule-based first (RSI, volume spike, moving average crossover), then LLM-assisted narrative confirmation
- [ ] Per-token timeline view: price chart + signal overlays exportable to Sheets or a local HTML report

## Phase 5 — Sentiment Model & Investment Simulator

Quantify market mood and back-test the bot's decisions before any real money is involved.

- [ ] Fear/Greed index: research existing models (CNN Fear & Greed, Alternative.me Crypto F&G, Santiment) and design a composite score from: RSS sentiment, Reddit engagement ratios, price momentum, volume, and social mentions
- [ ] Sentiment scoring pipeline: run the composite model each scan and store the score in the run log alongside sector scores
- [ ] Investment simulator: for each token the bot is confident in, simulate buying 10 € at the detected entry point and selling at the exit signal — track P&L, win rate, and drawdown over time
- [ ] Simulation report: exported to Sheets (one row per simulated trade) so efficiency of entry/exit logic can be reviewed and tuned

## Phase 6 — Live Trading & Deployment

Connect to real markets and run the bot permanently at minimal cost — only after the simulator shows consistent positive results.

- [ ] Exchange API integration: connect to a broker/exchange API (e.g. Kraken, Binance) to place real buy/sell orders — initially paper-trade mode only, mirroring the simulator
- [ ] Order management: position sizing, stop-loss, take-profit rules derived from Phase 4/5 signal logic
- [ ] Containerisation: package the full pipeline as a Docker container runnable on a cheap cloud instance (e.g. Fly.io free tier, Railway, or a ~$2/month VPS) — target cost in cents per month
- [ ] Observability: structured logs + alerting (e.g. Telegram or email) for run failures, degraded feeds, or triggered trade signals
