# Roadmap

---

## ✅ Phase 1 — Complete

- File logging + pending_issues writer
- fetch_with_retry (3 attempts, Retry-After backoff)
- Dead RSS feeds fixed; per-run in-memory cache
- config.json restructured (core / baseline / discovery / exclude pools)
- SECTOR_KEYWORDS pre-filter + filter_no_sector() (drops off-taxonomy posts)
- Token confidence scoring (multi-signal: mentions, spread, engagement, discovery)
- Sheets + Notion schema expansion
- Schema compliance fix (num_ctx=16384, selftext_max=400, _SCHEMA_REMINDER)

## ✅ Phase 2 — Complete

- [x] Discovery RSS layer (--discovery flag, 6 fetchable sources)
- [x] Tier classification (investment_quality / speculative)
- [x] Subreddit proposals (LLM suggests, human applies)
- [x] Cycle evidence local artifact (data/cycle_summary_latest.json)
- [x] Token tracking registry (config.json token_tracking wired)
- [x] Discovery source health monitoring (auto-flag dead feeds)
- [x] Google Sheets schema alignment (ensure_sheet_headers)

---

## 🔴 Phase 3 — Run Unattended (Blockers)

> Nothing in Phase 4+ is worth building until the bot can run reliably without a human watching it.
> These must be done in order — items 1 and 2 are prerequisites for everything else.

- [ ] **1. Swap Ollama → Groq API** — llama3.1:8b needs 8–10 GB RAM; no cheap cloud instance can host it. Groq runs the same model for free (14,400 req/day), reduces a run from ~5 min to ~10 sec, and unlocks cloud deployment. One function change in `_ollama_generate()`.
- [ ] **2. Fix TOKEN_SHORTLIST crash** — `clamp_scores(d2)` fails when the model returns strings in `sectors` instead of dicts. The bot crashes on most TOKEN_SHORTLIST runs. Must be fixed before scheduling.
- [ ] **3. Dockerfile + scheduled runs** — once Groq is in, the bot is a lightweight Python script. Package as Docker, schedule with GitHub Actions cron (`0 * * * *`) or a €4/month Hetzner VPS. Target: runs every hour at near-zero cost.
- [ ] **4. Fix degraded feeds** — Messari RSS returns `fetch_with_retry: unreachable`; StarknetCrypto returns 0 items every run. Mark as `fetchable: false` or replace. Unattended runs should not silently produce bad data.
- [ ] **5. Revisit `discovery_limit` default** — currently caps at 5 out of ~100 fetched items (95% dropped). Should be tuned once the pipeline is stable.
- [ ] **6. Multi-day trend scoring** — diff the ledger across runs to detect sectors rising or falling over time. Needed before the watchlist (Phase 4) is meaningful.

## 🟡 Phase 4 — Token Price Intelligence

> Track the tokens we discover and find when to act on them.

- [ ] **Active token watchlist** — a dedicated section of the pipeline for tokens we have shortlisted and want to monitor continuously, separate from the discovery ledger. Feeds from the `token_tracking` registry built in Phase 2.
- [ ] **Price history fetcher** — pull OHLCV data for watchlist tokens via CoinGecko or similar free API. Store locally (JSON or SQLite).
- [ ] **Entry/exit signal detection** — rule-based first (RSI, volume spike, moving average crossover), then LLM-assisted narrative confirmation from our existing sector/token analysis.
- [ ] **Per-token timeline report** — price chart + signal overlays, exportable to Sheets or a local HTML file for review.

## 🟡 Phase 5 — Sentiment Model & Investment Simulator

> Quantify market mood and validate the bot's decisions before any real money is involved.

- [ ] **Fear/Greed index** — research existing models (CNN Fear & Greed, Alternative.me Crypto F&G, Santiment) and design a composite score from: RSS sentiment, Reddit engagement ratios, price momentum, volume, and social mentions. Build and test against historical data before using it live.
- [ ] **Sentiment scoring pipeline** — run the composite model each scan and store the score in the run log alongside sector scores.
- [ ] **Investment simulator** — for each token the bot is confident in, simulate buying 10 € at the detected entry point and selling at the exit signal. Track P&L, win rate, and drawdown over time.
- [ ] **Simulation report** — export to Sheets (one row per simulated trade) so entry/exit logic can be reviewed and tuned. Do not proceed to Phase 6 until the simulator shows consistent positive results.

## 🔵 Phase 6 — Live Trading & Permanent Deployment

> Only after the simulator validates the strategy. Connect to real markets and run forever at minimal cost.

- [ ] **Exchange API — paper trade first** — connect to a broker/exchange API (Kraken or Binance recommended) in paper-trade mode, mirroring simulator decisions. Run in parallel with the simulator for at least 4 weeks before going live.
- [ ] **Live order management** — position sizing, stop-loss, and take-profit rules derived from Phase 4/5 signal logic. Start with small fixed amounts.
- [ ] **Permanent cloud deployment** — move from GitHub Actions to an always-on container on a cheap host (Fly.io free tier or a ~€4/month Hetzner VPS). Target: total running cost under €5/month including LLM inference.
- [ ] **Observability** — Telegram or email alerts for run failures, degraded feeds, and triggered trade signals. Essential once the bot runs without supervision.
