import argparse, json, os, pathlib, re, sys, time
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from zoneinfo import ZoneInfo
from collections import Counter
from urllib.parse import urlparse

import feedparser
import requests
from dotenv import load_dotenv
from notion_client import Client as NotionClient

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERROR": "❌", "STEP": "🔄"}
    print(f"[{ts}] {icons.get(level,'  ')} [{level}] {msg}")

_RUN_LOG_PATH: str | None = None

def open_run_log(run_id: str, run_mode: str) -> str:
    pathlib.Path("logs").mkdir(exist_ok=True)
    return f"logs/{datetime.now().strftime('%Y%m%d')}_{run_mode}_{run_id}.log"

def log_step(log_path: str, step: str, **data) -> None:
    if not log_path:
        return
    entry = {"ts": datetime.now().isoformat(), "step": step, **data}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

def write_pending_issue(*, run_id, run_mode, component, error_type,
                         url, detail, retry_count, outcome, action) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id, "run_mode": run_mode,
        "component": component, "error_type": error_type,
        "url": url, "detail": str(detail)[:500],
        "retry_count": retry_count, "outcome": outcome, "action": action,
    }
    path = pathlib.Path("tasks") / "pending_issues.jsonl"
    path.parent.mkdir(exist_ok=True)
    with open(str(path), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def fetch_with_retry(url, headers, timeout=30, max_retries=2,
                     *, run_id="", run_mode="", component="http_fetch"):
    backoff = [2, 5]
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 429:
                try:
                    wait = int(r.headers.get("Retry-After",
                               backoff[min(attempt, len(backoff)-1)]))
                except (ValueError, TypeError):
                    wait = backoff[min(attempt, len(backoff)-1)]
                log("WARN", f"429 [{component}] — waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < max_retries:
                wait = backoff[min(attempt, len(backoff)-1)]
                log("WARN", f"Attempt {attempt+1} failed [{component}]: {e} — retry in {wait}s")
                time.sleep(wait)
            else:
                log("ERROR", f"Failed after {max_retries+1} attempts [{component}]: {url}")
                if run_id:
                    write_pending_issue(
                        run_id=run_id, run_mode=run_mode, component=component,
                        error_type=type(e).__name__, url=url, detail=str(e),
                        retry_count=attempt, outcome="failed", action="check_pending_issues",
                    )
                raise
    raise RuntimeError("fetch_with_retry: unreachable")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_TAXONOMY = [
    "AI/Compute",
    "DePIN",
    "RWA/Tokenization",
    "L2/DA/Modular",
    "Interop/Messaging",
    "Security/Tooling",
    "DeFi (Revenue-driven)",
    "Institutional/ETFs",
    "Regulation/Policy",
    "Macro/Liquidity",
    "Other/Unknown",
]

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "AI/Compute":            ["ai", "artificial intelligence", "gpu", "compute", "inference",
                              "agent", "llm", "neural", "machine learning"],
    "DePIN":                 ["depin", "physical infrastructure", "iot", "wireless", "hotspot",
                              "sensor", "helium", "hivemapper"],
    "RWA/Tokenization":      ["rwa", "real world asset", "tokenize", "tokenization",
                              "treasury", "bond", "real estate", "commodity"],
    "L2/DA/Modular":         ["layer2", "l2", "rollup", "zk", "optimistic", "data availability",
                              "modular", "celestia", "eigenlayer", "arbitrum", "starknet"],
    "Interop/Messaging":     ["bridge", "cross-chain", "interop", "messaging", "ibc",
                              "wormhole", "layerzero", "axelar"],
    "Security/Tooling":      ["audit", "security", "tooling", "sdk", "dev tool", "wallet",
                              "multisig", "exploit", "vulnerability", "hack"],
    "DeFi (Revenue-driven)": ["defi", "dex", "amm", "lending", "yield", "tvl", "revenue",
                              "liquidity", "swap", "governance", "staking", "aave", "uniswap"],
    "Institutional/ETFs":    ["etf", "institutional", "blackrock", "grayscale", "fidelity",
                              "custody", "regulated", "asset manager"],
    "Regulation/Policy":     ["sec", "regulation", "policy", "compliance", "cftc", "mica",
                              "legislation", "congress", "enforcement", "ban"],
    "Macro/Liquidity":       ["macro", "liquidity", "fed", "interest rate", "inflation",
                              "recession", "dollar", "monetary", "rate hike", "rate cut"],
}

def tag_post_sectors(post: dict) -> list[str]:
    txt = " ".join([
        post.get("title", "") or "",
        post.get("summary", "") or "",
        post.get("selftext", "") or "",
    ]).lower()
    return [s for s, kws in SECTOR_KEYWORDS.items() if any(kw in txt for kw in kws)]

def filter_no_sector(items: list[dict]) -> tuple[list[dict], dict]:
    from collections import Counter
    kept, discarded, per_sector = [], 0, Counter()
    for it in items:
        sectors = tag_post_sectors(it)
        if sectors:
            it["_matched_sectors"] = sectors
            per_sector.update(sectors)
            kept.append(it)
        else:
            discarded += 1
    return kept, {"discarded": discarded, "kept_per_sector": dict(per_sector)}

# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS — one per job so each call has a tight, clear contract
# ═══════════════════════════════════════════════════════════════════════════════

_HARD_RULES = """
HARD RULES (ANTI-HALLUCINATION):
1) Never invent facts, metrics, dates, returns, partnerships, listings,
   tokenomics, unlocks, audits, incidents, TVL, fees, revenue, users, or dev stats.
2) Any claim about events / surges / latest / regulatory / price moves
   MUST cite source URL + date from the evidence provided.
3) Separate clearly: OBSERVATIONS (sourced) | INTERPRETATION | HYPOTHESES |
   UNCERTAINTIES | INVALIDATIONS.
4) No meme coins / influencer-pump projects. If driver = culture pump → Rejected.
5) No certainty language. Use probabilities + confidence (High / Med / Low).
6) Output a single JSON OBJECT (not array). Begin response with <DATA_JSON>.
"""

SYSTEM_PROMPT_SECTORS_ONLY = """You are a crypto analyst. Analyse the Reddit posts provided and identify sector trends.

FORBIDDEN PHRASES (do not use these):
- "There is limited discussion"
- "One post mentions"
- "could be related to"
- "may be"

RULES:
- sector must be one of the ALLOWED SECTORS
- for/against/invalidations: quote or paraphrase specific things from the posts
- If a sector has real signal, score it 40-80. If almost no signal, score 10-30.
- Only include sectors you actually see evidence for in the posts
- tokens must be empty list []
- Output ONLY <DATA_JSON>...</DATA_JSON> then <MARKDOWN>...</MARKDOWN>

EXAMPLE of good "for" entries (specific, not vague):
  "for": [
    "Polkadot dev built open-source extrinsic builder with type-safe inputs (r/Polkadot)",
    "AI agent marketplace settling USDC on Base mainnet, 37 listings live (r/ethdev)"
  ]

EXAMPLE of bad "for" entries (do not do this):
  "for": ["zk-SNARKs can be used to verify post-quantum signatures"]

EXAMPLE OUTPUT:
<DATA_JSON>
{
  "meta": {"run_id":"","generated_at":"","run_mode":"","time_window":"","cycles":[],"regime":{"label":"Unknown","confidence":"Low","sources":[]}},
  "sectors": [
    {
      "sector": "Security/Tooling",
      "score": 55,
      "confidence": "Med",
      "status": "Speculative",
      "narrative": "A dev posted an open-source extrinsic builder for Polkadot with type-safe SCALE encoding and wallet integration. Separately, a zk-SNARK post-quantum signature verifier was shared on r/ethereum.",
      "for": ["Relaycode open-source extrinsic builder shipped with 22 input components (r/Polkadot)", "Post-quantum zk-SNARK verifier project posted on r/ethereum"],
      "against": ["Both are dev tools, not protocols with token traction"],
      "invalidations": ["No TVL or user adoption metrics cited in either post"],
      "top_entities": ["Polkadot", "Relaycode"],
      "sources": [{"url": "https://www.reddit.com/r/Polkadot/comments/1rgk7o7/", "date": "2026-02-28"}]
    }
  ],
  "tokens": [],
  "questions_for_user": ["Is Polkadot tooling gaining developer momentum?"]
}
</DATA_JSON>
<MARKDOWN>
## OBSERVATIONS
Developer tooling activity visible in Polkadot and Ethereum ecosystems.

## INTERPRETATION
Build activity without token catalysts suggests early-cycle developer interest.

## WHAT WOULD CHANGE MY MIND
TVL or user growth metrics from these projects would upgrade confidence.
</MARKDOWN>"""

SYSTEM_PROMPT_TOKENS_ONLY = _HARD_RULES + """
TASK: Produce a TOKEN SHORTLIST only from the focus sectors. sectors must be [].

OUTPUT format — exactly two blocks, nothing else:
<DATA_JSON>
{ single valid JSON object }
</DATA_JSON>
<MARKDOWN>
3-6 sentences: which tokens made the cut, why, and key invalidations.
</MARKDOWN>

TOKEN RULES:
- ONLY include symbols from TOKEN CANDIDATES list.
- REJECT tokens with mention_count < 2 AND no non-Reddit primary source link.
- REJECT anything that looks like an English word (EXPOSE, BEWARE, LEAK, etc.).
- name / chain: set "Unknown" unless explicitly stated in evidence.
- spike_score: integer 0-100.

JSON SCHEMA:
{
  "meta": {
    "run_id":"","generated_at":"","run_mode":"","time_window":"","cycles":[],
    "regime":{"label":"Unknown","confidence":"Low","sources":[]}
  },
  "sectors":[],
  "tokens":[{
    "sector":"","symbol":"","name":"Unknown","chain":"Unknown","spike_score":0,
    "confidence":"Low","status":"Speculative","thesis":"",
    "catalysts":[],"traction":[],"tokenomics_risks":[],
    "security":[],"liquidity":[],"invalidations":[],
    "sources":[{"url":"","date":""}]
  }],
  "questions_for_user":[]
}

TIER RULES:
- Every token MUST include "tier": "investment_quality" OR "speculative".
- investment_quality: token appeared in NON_REDDIT_DISCOVERY_SOURCES OR confidence score >= 50
  AND subreddit_spread >= 3. Also include a 1-sentence "explanation" field.
- speculative: everything else. Default to "speculative" when in doubt.
- Every token MUST include "explanation": one sentence rationale for the tier assignment.

SUBREDDIT PROPOSALS (always output, even if empty):
- Based on what sectors/tokens you see, propose up to 3 subreddit adjustments to improve signal.
- ONLY propose subreddits that clearly exist and are crypto-relevant.
- Output as top-level "subreddit_proposals" array alongside meta/sectors/tokens.

SCHEMA ADDITIONS:
tokens[*] += { "tier": "speculative", "explanation": "one sentence" }
Top-level += "subreddit_proposals": [{"action":"add"|"remove","name":"SubName","reason":"..."}]
"""

SYSTEM_PROMPT_CYCLE_MAP = _HARD_RULES + """
TASK: Build a HISTORICAL CYCLE PLAYBOOK from the evidence pack below.
Map: cycles → repeating sector waves → early indicators → invalidations.

OUTPUT format — EXACTLY these two blocks and nothing else:
<DATA_JSON>
{ your analysis as a single JSON object }
</DATA_JSON>
<MARKDOWN>
## CYCLE ANCHORS (sourced)
## REPEATING PATTERNS
## EARLY INDICATORS
## HYPOTHESES (next waves)
## INVALIDATION TESTS
</MARKDOWN>

CRITICAL: The JSON object MUST contain exactly these top-level keys:
  meta, sectors, tokens, questions_for_user
Do NOT invent your own keys like "ethereum", "erc20", "ethereum_forks".

EXAMPLE OF CORRECT OUTPUT STRUCTURE (fill with real content from evidence):
<DATA_JSON>
{
  "meta": {
    "run_id": "CYCLE_MAP_BUILD-example",
    "generated_at": "2024-01-01T00:00:00",
    "run_mode": "CYCLE_MAP_BUILD",
    "time_window": "historical",
    "cycles": ["2017 ICO boom", "2020-2021 DeFi summer", "2021-2022 NFT wave"],
    "regime": {"label": "Unknown", "confidence": "Low", "sources": []}
  },
  "sectors": [
    {
      "sector": "DeFi (Revenue-driven)",
      "score": 75,
      "confidence": "Med",
      "status": "Verified",
      "narrative": "DeFi protocols like Uniswap and Compound led the 2020 cycle via yield farming and governance token distribution.",
      "for": ["Uniswap UNI launch in Sep 2020 triggered liquidity mining wave", "Compound COMP distribution created yield farming narrative"],
      "against": ["High gas fees excluded retail", "Many protocols had unaudited code"],
      "invalidations": ["Regulatory crackdown on DEXs could end cycle", "L1 congestion pricing out smaller participants"],
      "top_entities": ["Uniswap", "Compound", "Aave"],
      "sources": [{"url": "https://blog.uniswap.org/uni", "date": "2020-09-17"}]
    }
  ],
  "tokens": [
    {
      "sector": "DeFi (Revenue-driven)",
      "symbol": "UNI",
      "name": "Uniswap",
      "chain": "Ethereum",
      "spike_score": 70,
      "confidence": "Med",
      "status": "Verified",
      "thesis": "UNI was the first major retroactive airdrop, setting precedent for governance token distribution cycles.",
      "catalysts": ["Retroactive airdrop to early users", "Governance rights over protocol"],
      "traction": ["$1B+ TVL within weeks of launch"],
      "tokenomics_risks": ["Large team/investor allocation"],
      "security": ["Audited by multiple firms"],
      "liquidity": ["Deep liquidity on own protocol"],
      "invalidations": ["SEC action on DEX governance tokens"],
      "sources": [{"url": "https://blog.uniswap.org/uni", "date": "2020-09-17"}]
    }
  ],
  "questions_for_user": ["Which cycle phase do you believe we are currently in?"]
}
</DATA_JSON>

Now produce your real analysis using ONLY the evidence pack provided.
Every claim must cite a source URL + date from that evidence. Do not invent facts.

VARIABLE FRAMEWORK — analyse these signals when building the cycle playbook:

MACRO: Fed funds rate direction (hiking/holding/cutting); M2 YoY growth;
DXY trend; Fed balance sheet trajectory.

BITCOIN ON-CHAIN: Halving supply shock timing; MVRV-Z (over/undervalued);
SOPR (profit-taking signal); exchange net inflows (distribution) vs outflows (accumulation).

SECTORS: TVL growth rate by chain; DEX volume as % of total;
dominant narrative per cycle phase (yield, NFT, L2, RWA, AI);
sector rotation sequence.

TOKENS — for every token in evidence, assign:
  growth_type: "quick" (spike <3 months then retrace),
               "sustained" (>6 months with fundamental backing),
               "mixed" (pump then partial sustained recovery)
  sustainability_correlates: list from [revenue, DAU, tokenomics_quality,
    emission_schedule, protocol_revenue, audit_status, institutional_adoption]

BTC DRIVER ANALYSIS — for each cycle:
  btc_up_driver: primary catalyst (e.g. halving supply shock, ETF inflows, macro liquidity)
  btc_down_driver: primary catalyst (e.g. regulatory shock, macro tightening, CeFi collapse)
  Cite source URL + date for every driver claim.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# REDDIT RSS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def rss_url(subreddit: str, feed: str) -> str:
    if feed == "new":
        return f"https://www.reddit.com/r/{subreddit}/new.rss"
    return f"https://www.reddit.com/r/{subreddit}/{feed}/.rss?sort={feed}"


def resolve_cycle_phase(args, cfg: dict) -> str | None:
    """Return the active cycle phase: CLI arg > config.json > None."""
    if getattr(args, "cycle_phase", None):
        return args.cycle_phase
    return cfg.get("cycle_phase") or None


def resolve_phase_subreddits(phase: str | None, cycle_data: dict,
                              fallback_subreddits: list) -> list:
    """Return subreddits for the given phase, or fallback_subreddits if phase is None."""
    if not phase:
        return fallback_subreddits
    return cycle_data.get("phases", {}).get(phase, {}).get("subreddits", fallback_subreddits)


def load_subreddits_from_config(cfg: dict, use_discovery: bool = False) -> list[dict]:
    """Return effective subreddit list.
    use_discovery=False → core_subreddits → baseline_subreddits → subreddits, apply exclude filter.
    use_discovery=True → merge core + discovery, deduped by name, apply exclude filter."""
    exclude = {e["name"].lower() for e in cfg.get("exclude_subreddits", [])}
    if not use_discovery:
        pool = (cfg.get("core_subreddits")
                or cfg.get("baseline_subreddits")
                or cfg.get("subreddits", []))
        return [s for s in pool if s.get("name", "").lower() not in exclude]
    baseline  = (cfg.get("core_subreddits")
                 or cfg.get("baseline_subreddits")
                 or cfg.get("subreddits", []))
    discovery = cfg.get("discovery_subreddits", [])
    seen: set[str] = set()
    merged: list[dict] = []
    for s in baseline + discovery:
        key = s.get("name", "").lower()
        if key and key not in seen and key not in exclude:
            seen.add(key)
            merged.append(s)
    return merged


def parse_entry_time(entry) -> datetime | None:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)


def fetch_reddit_items(cfg: dict, since_utc: datetime,
                       run_id: str = "", run_mode: str = "") -> list[dict]:
    items, seen = [], set()
    headers = {"User-Agent": "crypto-radar/1.0 (rss trend miner)"}
    for s in cfg["subreddits"]:
        for feed in s["feeds"]:
            url = rss_url(s["name"], feed)
            log("STEP", f"Fetching r/{s['name']} [{feed}] ...")
            try:
                r = fetch_with_retry(url, headers, timeout=30,
                                     run_id=run_id, run_mode=run_mode,
                                     component=f"reddit/{s['name']}/{feed}")
            except requests.RequestException as e:
                log("WARN", f"Skipping r/{s['name']} [{feed}]: {e}")
                continue
            parsed = feedparser.parse(r.text)
            log("INFO", f"  → {len(parsed.entries)} entries received")
            for e in parsed.entries[: cfg["max_items_per_feed"]]:
                dt = parse_entry_time(e)
                if not dt or dt < since_utc:
                    continue
                link = e.link
                if link in seen:
                    continue
                seen.add(link)
                items.append({
                    "platform":      "reddit",
                    "subreddit":     s["name"],
                    "feed":          feed,
                    "title":         e.get("title", ""),
                    "url":           link,
                    "published_utc": dt.isoformat(),
                    "author":        e.get("author", ""),
                    "summary":       (e.get("summary", "") or "")[:2000],
                })
    items.sort(key=lambda x: x["published_utc"], reverse=True)
    log("OK", f"Fetched {len(items)} unique items across all feeds")
    return items


_DISCOVERY_CACHE: dict[str, bytes] = {}


def fetch_discovery_rss_items(sources_path: str, max_per_feed: int = 20,
                               run_id: str = "", run_mode: str = "") -> list[dict]:
    """Parse RSS discovery sources via feedparser. Returns reddit-schema-compatible item dicts."""
    if not os.path.exists(sources_path):
        log("WARN", f"Discovery sources not found: {sources_path} — skipping")
        return []
    raw     = json.load(open(sources_path, "r", encoding="utf-8"))
    sources = raw.get("sources", []) if isinstance(raw, dict) else raw
    rss_src = [s for s in sources if s.get("type") == "rss" and s.get("fetchable", False)]
    items: list[dict] = []
    seen:  set[str]   = set()
    headers = {"User-Agent": "crypto-radar/1.0 (rss trend miner)"}
    for s in rss_src:
        url, label = s.get("url", ""), s.get("label", "")
        try:
            if url in _DISCOVERY_CACHE:
                parsed = feedparser.parse(_DISCOVERY_CACHE[url])
            else:
                r = fetch_with_retry(url, headers, timeout=30,
                                     run_id=run_id, run_mode=run_mode,
                                     component=f"discovery/{label}")
                _DISCOVERY_CACHE[url] = r.content
                parsed = feedparser.parse(r.text)
            if parsed.bozo:
                log("WARN", f"  Discovery RSS bozo [{label}]: {parsed.bozo_exception}")
            count  = 0
            for e in parsed.entries[:max_per_feed]:
                link = getattr(e, "link", "") or ""
                if link in seen:
                    continue
                seen.add(link)
                dt = parse_entry_time(e)
                items.append({
                    "platform":      "discovery",
                    "source_label":  label,
                    "source_url":    url,
                    "title":         e.get("title", ""),
                    "url":           link,
                    "published_utc": dt.isoformat() if dt else "",
                    "summary":       (e.get("summary", "") or "")[:2000],
                    "selftext":      "",
                    "subreddit":     "",
                    "reddit_score":  0,
                    "num_comments":  0,
                    "engagement":    0,
                })
                count += 1
            log("INFO", f"  Discovery RSS [{label}]: {count} items")
            if count == 0 and run_id:
                write_pending_issue(
                    run_id=run_id, run_mode=run_mode, component=f"discovery/{label}",
                    error_type="ZeroItems", url=url, detail="Feed returned 0 items",
                    retry_count=0, outcome="zero_items", action="check_pending_issues",
                )
        except requests.RequestException as exc:
            log("WARN", f"  Discovery RSS failed [{label}]: {exc}")
        except Exception as exc:
            log("WARN", f"  Discovery RSS failed [{label}]: {exc}")
    log("INFO", f"Discovery: {len(items)} items from {len(rss_src)} RSS feeds")
    return items

# ═══════════════════════════════════════════════════════════════════════════════
# LEDGER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def append_ledger(path: str, run_id: str, items: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({"run_id": run_id, **it}, ensure_ascii=False) + "\n")


def load_recent_ledger(path: str, since_utc: datetime, limit: int = 250) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                dt = datetime.fromisoformat(row["published_utc"].replace("Z", "+00:00"))
                if dt >= since_utc:
                    out.append(row)
            except Exception:
                pass
    # Deduplicate by URL — keep most recent occurrence only
    seen_urls = set()
    deduped = []
    for row in sorted(out, key=lambda x: x["published_utc"], reverse=True):
        u = row.get("url", "")
        if u and u in seen_urls:
            continue
        seen_urls.add(u)
        deduped.append(row)
    return deduped[:limit]


def purge_old_ledger(path: str, keep_hours: int = 72) -> None:
    if not os.path.exists(path):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
    kept = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                dt = datetime.fromisoformat(row["published_utc"].replace("Z", "+00:00"))
                if dt >= cutoff:
                    kept.append(line)
            except Exception:
                pass
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(kept)
    log("INFO", f"Ledger purged: kept {len(kept)} entries from last {keep_hours}h")

# ═══════════════════════════════════════════════════════════════════════════════
# HTML / TEXT UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&quot;", '"')
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#32;", " "))
    return re.sub(r"\s+", " ", text).strip()


def enrich_reddit_post(url: str, headers: dict) -> dict:
    """Fetch full post body + metadata from Reddit's free public JSON API (no auth)."""
    try:
        jurl = url.rstrip("/") + ".json?raw_json=1"
        r = fetch_with_retry(jurl, headers, timeout=20, max_retries=2, component="enrich")
        post = r.json()[0]["data"]["children"][0]["data"]
        return {
            "selftext":     strip_html(post.get("selftext") or "")[:2500],
            "num_comments": post.get("num_comments"),
            "reddit_score": post.get("score"),
            "outbound_url": post.get("url_overridden_by_dest") or "",
        }
    except Exception:
        return {"selftext": "", "num_comments": None,
                "reddit_score": None, "outbound_url": ""}


def trim_ledger_for_prompt(items: list[dict], max_items: int = 30) -> list[dict]:
    """
    Keep only fields the model needs and clean the text.
    NOTE: engagement filtering happens AFTER enrichment, not here.
    """
    trimmed = []
    for it in items:
        score = it.get("reddit_score") or 0
        comms = it.get("num_comments") or 0
        trimmed.append({
            "published_utc": it.get("published_utc", ""),
            "title":         it.get("title", ""),
            "subreddit":     it.get("subreddit", ""),
            "url":           it.get("url", ""),
            "summary":       strip_html(it.get("summary", "") or "")[:800],
            "selftext":      it.get("selftext", ""),
            "reddit_score":  score,
            "num_comments":  comms,
            "outbound_url":  it.get("outbound_url", ""),
            "engagement":    score + 2 * comms,
        })
    return trimmed[:max_items]

# ═══════════════════════════════════════════════════════════════════════════════
# MEME FILTER
# ═══════════════════════════════════════════════════════════════════════════════

MEME_RE = re.compile(
    r"\b(memecoin|meme\s*coin|pepe|doge|shiba|shib|bonk|wif|floki|wojak)\b",
    re.I
)

def filter_memes(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        txt = f"{it.get('title','')} {it.get('summary','')} {it.get('selftext','')}"
        if MEME_RE.search(txt):
            log("INFO", f"  Meme-filtered: {it.get('title','')[:70]}")
            continue
        out.append(it)
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN CANDIDATE EXTRACTION  (high-precision)
# ═══════════════════════════════════════════════════════════════════════════════

# Only match explicit $TICKER or (TICKER) — never bare English words
TOKEN_RE = re.compile(r"\$([A-Z]{2,6})\b|\(([A-Z]{2,6})\)\b")

# Post must contain a crypto-context keyword to be considered at all
CONTEXT_RE = re.compile(
    r"\b(ticker|token|coin|airdrop|launch|mainnet|testnet|listing|exchange|"
    r"dex|lending|protocol|defi|nft|blockchain|wallet|staking|yield|swap|governance)\b",
    re.I,
)

TOKEN_BLACKLIST = {
    "USD","USDT","USDC","EU","UK","US","SEC","ETF","AI","DAO","CEO","CEX","DEX",
    "NFT","API","URL","DEFI","THE","FOR","AND","NOT","ARE","YOU","BUT","ALL",
    "NEW","ITS","HOW","WHAT","THIS","WITH","FROM","THAT","BEEN","HAVE","WILL",
    "DID","GET","HAS","WAS","CAN","OUT","NOW","GMT","UTC",
}

_ENGLISH_WORDS = {
    "expose","beware","dirtiest","warning","collapse","bubble","secret",
    "leak","files","pump","dump","scam","hack","crash","moon","bull","bear",
    "top","yes","no","go","up","down",
}

FUNDAMENTALS_KEYWORDS = re.compile(
    r"\b(revenue|tvl|fees|protocol|tokenomics|staking|yield|governance|"
    r"fundrais|raise|series\s+[a-c]|valuation|audit|roadmap|mainnet|"
    r"developer|on.chain|treasury|total.value.locked|protocol.revenue)\b", re.I)

RISK_KEYWORDS = re.compile(
    r"\b(rug|scam|hack|exploit|drain|ponzi|honeypot|unaudited|"
    r"anonymous.team|no.audit|exit.scam|suspicious)\b", re.I)


def looks_like_english_word(sym: str) -> bool:
    return sym.lower() in _ENGLISH_WORDS


def extract_token_candidates(trimmed_items: list[dict],
                             max_candidates: int = 30) -> list[str]:
    found, seen = [], set()
    for it in trimmed_items:
        text = f"{it.get('title','')} {it.get('summary','')} {it.get('selftext','')}"
        if not CONTEXT_RE.search(text):
            continue
        for a, b in TOKEN_RE.findall(text):
            m = (a or b).upper()
            if m in TOKEN_BLACKLIST or len(m) < 2 or len(m) > 6:
                continue
            if looks_like_english_word(m):
                continue
            if m not in seen:
                seen.add(m)
                found.append(m)
    return found[:max_candidates]


def candidate_strength(trimmed_items: list[dict],
                       candidates: list[str]) -> dict[str, int]:
    """Count distinct posts that mention each candidate symbol."""
    counts: Counter = Counter()
    for it in trimmed_items:
        txt = (
            it.get("title", "") + " " +
            it.get("summary", "") + " " +
            it.get("selftext", "")
        ).upper()
        for c in candidates:
            if f"${c}" in txt or f"({c})" in txt:
                counts[c] += 1
    return dict(counts)


def _compute_tier(cs: dict) -> str:
    c  = cs.get("confidence", 0)
    dc = cs.get("discovery_count", 0)
    ss = cs.get("subreddit_spread", 0)
    return "investment_quality" if (c >= 50 and (dc > 0 or ss >= 3)) else "speculative"


def _build_score_explanation(m: int, ss: int, dc: int, fund: bool, risk: bool, tier: str) -> str:
    parts = [f"Reddit:{m}m/{ss}s"]
    if dc:   parts.append(f"{dc} discovery hit(s)")
    if fund: parts.append("fundamentals signal")
    if risk: parts.append("RISK FLAG")
    parts.append(f"→ {tier}")
    return " + ".join(parts)


def token_confidence_score(
    candidates: list[str],
    ledger_items: list[dict],
    discovery_items: list[dict] | None = None,
) -> dict[str, dict]:
    """
    Multi-signal confidence score per token candidate.

    Returns per-symbol dict with keys:
      mentions, subreddit_spread, engagement_weight, discovery_count,
      discovery_sources, fundamentals_hint, risk_flag, confidence (0-100),
      tier, explanation.
    """
    mentions: Counter        = Counter()
    subreddits: dict         = {}   # symbol -> set of subreddits
    engagement: Counter      = Counter()

    for it in ledger_items:
        txt = (
            it.get("title", "") + " " +
            it.get("summary", "") + " " +
            it.get("selftext", "")
        ).upper()
        sub = it.get("subreddit", "")
        eng = (it.get("reddit_score", 0) or 0) + 2 * (it.get("num_comments", 0) or 0)
        for c in candidates:
            if f"${c}" in txt or f"({c})" in txt:
                mentions[c] += 1
                subreddits.setdefault(c, set()).add(sub)
                engagement[c] += eng

    result = {}
    for symbol in candidates:
        m               = mentions.get(symbol, 0)
        ss              = len(subreddits.get(symbol, set()))
        ew              = engagement.get(symbol, 0)
        engagement_weight = ew

        # Discovery signals
        discovery_count  = 0
        fundamentals_hit = False
        risk_hit         = False
        discovery_labels: list[str] = []
        if discovery_items:
            sym_upper = symbol.upper()
            for di in discovery_items:
                text = f"{di.get('title','')} {di.get('summary','') or di.get('selftext','')}".upper()
                if f"${sym_upper}" in text or f" {sym_upper} " in text or f"({sym_upper})" in text:
                    discovery_count += 1
                    discovery_labels.append(di.get("source_label", di.get("source_url", "")))
                    raw_text = f"{di.get('title','')} {di.get('summary','')}"
                    if FUNDAMENTALS_KEYWORDS.search(raw_text):
                        fundamentals_hit = True
        # Risk check across all items (reddit + discovery)
        for item in (ledger_items + (discovery_items or [])):
            if RISK_KEYWORDS.search(f"{item.get('title','')} {item.get('selftext','')} {item.get('summary','')}"):
                risk_hit = True
                break

        # Revised scoring formula
        raw = (
              m               * 8
            + ss              * 12
            + min(engagement_weight // 100, 25)
            + discovery_count  * 20
            + (10 if fundamentals_hit else 0)
            - (20 if risk_hit        else 0)
        )
        confidence = max(0, min(int(raw), 100))
        tier       = _compute_tier({"confidence": confidence, "discovery_count": discovery_count,
                                    "subreddit_spread": ss})
        result[symbol] = {
            "mentions":          m,
            "subreddit_spread":  ss,
            "engagement_weight": engagement_weight,
            "discovery_count":   discovery_count,
            "discovery_sources": discovery_labels[:5],
            "fundamentals_hint": fundamentals_hit,
            "risk_flag":         risk_hit,
            "confidence":        confidence,
            "tier":              tier,
            "explanation":       _build_score_explanation(m, ss, discovery_count,
                                                          fundamentals_hit, risk_hit, tier),
        }
    return result


def has_non_reddit_source(sources: list[dict]) -> bool:
    """True if at least one source URL is outside reddit.com."""
    for s in (sources or []):
        u = (s.get("url") or "").strip()
        if not u:
            continue
        dom = (urlparse(u).netloc or "").lower()
        if dom and "reddit.com" not in dom:
            return True
    return False


def generate_subreddit_proposals(llm_proposals: list[dict], cfg: dict) -> dict:
    """Post-process LLM subreddit proposals. Output only — does NOT modify config.json."""
    current = {
        s["name"].lower()
        for pool in ("core_subreddits", "baseline_subreddits", "discovery_subreddits", "subreddits")
        for s in cfg.get(pool, [])
    }
    result: dict = {
        "notice": "HUMAN REVIEW REQUIRED — edit discovery_subreddits in config.json to apply.",
        "add":    [],
        "remove": [],
    }
    for p in (llm_proposals or []):
        action = (p.get("action") or "").lower()
        name   = (p.get("name") or "").strip()
        reason = (p.get("reason") or "").strip()
        if not name:
            continue
        if action == "add" and name.lower() not in current:
            result["add"].append({"name": name, "reason": reason})
        elif action == "remove" and name.lower() in current:
            result["remove"].append({"name": name, "reason": reason})
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA CALLERS
# ═══════════════════════════════════════════════════════════════════════════════

def _ollama_generate(model: str, system: str, prompt: str) -> str:
    payload = {
        "model":  model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 4096,
            "num_ctx":     8192,
        },
    }
    r = requests.post("http://localhost:11434/api/generate",
                      json=payload, timeout=300)
    r.raise_for_status()
    raw = r.json().get("response", "")
    log("INFO", f"Ollama responded with {len(raw)} chars")
    # Recovery: model forgot opening tag but returned raw JSON
    if "<DATA_JSON>" not in raw and raw.strip().startswith("{"):
        raw = "<DATA_JSON>\n" + raw
    return raw


def call_ollama_sectors(model: str, trimmed: list[dict]) -> str:
    prompt = (
        "OUTPUT ONLY the two required XML-tagged blocks. No prose.\n\n"
        f"ALLOWED SECTORS: {', '.join(SECTOR_TAXONOMY)}\n\n"
        "REDDIT POSTS (ONLY evidence; cite url + published_utc for every claim):\n"
        + json.dumps(trimmed, ensure_ascii=False, indent=2)
        + "\n\nBegin your response with <DATA_JSON> now:"
    )
    log("INFO", f"Sending {len(trimmed)} posts to model ({len(prompt)} prompt chars)")
    log("STEP", f"Calling Ollama [{model}] — SECTORS pass ...")
    return _ollama_generate(model, SYSTEM_PROMPT_SECTORS_ONLY, prompt)


def call_ollama_tokens(model: str, trimmed: list[dict], focus_sectors: list[str],
                       token_candidates: list[str],
                       token_strength: dict[str, int],
                       confidence_scores: dict[str, dict] | None = None,
                       discovery_snippets: list[dict] | None = None) -> str:
    confidence_block = ""
    if confidence_scores:
        confidence_block = (
            "TOKEN_CONFIDENCE_SCORES (mentions/subreddit_spread/engagement_weight/confidence 0-100):\n"
            + json.dumps(confidence_scores, ensure_ascii=False)
            + "\n"
        )
    discovery_block = ""
    if discovery_snippets:
        slim = [
            {"label": d.get("source_label",""), "title": d.get("title",""),
             "snippet": (d.get("summary","") or "")[:400]}
            for d in discovery_snippets if d.get("platform") == "discovery"
        ][:12]
        if slim:
            discovery_block = (
                "NON_REDDIT_DISCOVERY_SOURCES (token mention here = external signal; "
                "fundamentals language = investment_quality hint):\n"
                + json.dumps(slim, ensure_ascii=False) + "\n"
            )
    prompt = (
        "OUTPUT ONLY the two required XML-tagged blocks. No prose.\n\n"
        f"FOCUS SECTORS (only shortlist tokens in these sectors): {focus_sectors}\n"
        f"TOKEN CANDIDATES: {token_candidates}\n"
        f"TOKEN_MENTION_COUNTS (require >=2 or non-Reddit primary source): {token_strength}\n"
        + confidence_block
        + discovery_block
        + "\nREDDIT POSTS (ONLY evidence):\n"
        + json.dumps(trimmed, ensure_ascii=False, indent=2)
        + "\n\nBegin your response with <DATA_JSON> now:"
    )
    log("STEP", f"Calling Ollama [{model}] — TOKENS pass ...")
    return _ollama_generate(model, SYSTEM_PROMPT_TOKENS_ONLY, prompt)


def call_ollama_cycle(model: str, evidence_pack: list[dict],
                      cycle_meta: dict | None = None) -> str:
    # Send only label + url + date_hint + first 1000 chars of snippet
    # to keep total prompt under ~12k chars
    slim_pack = [
        {
            "label":     e.get("label", ""),
            "url":       e.get("url", ""),
            "date_hint": e.get("date_hint", "Unknown"),
            "snippet":   (e.get("snippet", "") or "")[:1000],
        }
        for e in evidence_pack
        if not e.get("snippet", "").startswith("[FETCH_FAILED]")
    ]
    cycle_context_block = ""
    if cycle_meta:
        cycle_context_block = (
            "\nCYCLE CONTEXT (use this to frame your analysis):\n"
            + json.dumps({
                "label":             cycle_meta.get("label", ""),
                "time_boundaries":   cycle_meta.get("time_boundaries", {}),
                "key_events":        cycle_meta.get("key_events", []),
                "macro_context":     cycle_meta.get("macro_context", ""),
                "tracked_variables": cycle_meta.get("tracked_variables", {}),
            }, ensure_ascii=False, indent=2)
            + "\n"
        )
    prompt = (
        "OUTPUT ONLY the two required XML-tagged blocks. No prose.\n\n"
        f"ALLOWED SECTORS: {', '.join(SECTOR_TAXONOMY)}\n\n"
        + cycle_context_block
        + "EVIDENCE PACK (cite url + date_hint for every claim):\n"
        + json.dumps(slim_pack, ensure_ascii=False, indent=2)
        + "\n\nBegin your response with <DATA_JSON> now:"
    )
    log("STEP", f"Calling Ollama [{model}] — CYCLE MAP pass ...")
    return _ollama_generate(model, SYSTEM_PROMPT_CYCLE_MAP, prompt)

# ═══════════════════════════════════════════════════════════════════════════════
# CYCLE MAP EVIDENCE BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"\s+\d{1,2},\s+\d{4}\b"
)

def _infer_date(snippet: str) -> str:
    m = DATE_RE.search(snippet or "")
    return m.group(0) if m else "Unknown"


def _collect_cycle_sources(raw: dict, cycle_filter: str | None = None) -> list[dict]:
    """
    Aggregate sources from cycle_sources.json, deduplicated by URL.
    Order: 1) legacy_cycle_evidence (always)  2) cycles[filter] or all cycles
           3) categories[*].sources filtered by cycle_tags
    """
    seen_urls: set[str] = set()
    out: list[dict] = []

    def _add(entry: dict) -> None:
        url = (entry.get("url") or "").strip()
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        out.append(entry)

    for entry in raw.get("legacy_cycle_evidence", []):
        _add(entry)

    cycles_block = raw.get("cycles", {})
    if cycle_filter:
        for entry in cycles_block.get(cycle_filter, {}).get("sources", []):
            _add(entry)
    else:
        for cycle_obj in cycles_block.values():
            for entry in cycle_obj.get("sources", []):
                _add(entry)

    for cat_obj in raw.get("categories", {}).values():
        for entry in cat_obj.get("sources", []):
            tags = entry.get("cycle_tags", [])
            if cycle_filter and cycle_filter not in tags:
                continue
            _add(entry)

    return out


def build_cycle_evidence(sources_path: str, cache_path: str,
                         refresh: bool, cycle_filter: str | None = None) -> list[dict]:
    """
    For each URL in cycle_sources.json: fetch page, strip HTML, cache result.
    On subsequent runs the cache is used unless --refresh-cycle-sources is passed.
    """
    headers = {"User-Agent": "crypto-radar/1.0 (cycle map builder)"}

    cache: dict = {}
    if os.path.exists(cache_path) and not refresh:
        try:
            cache = json.load(open(cache_path, "r", encoding="utf-8"))
            log("INFO", f"Cycle cache loaded: {len(cache)} entries")
        except Exception:
            cache = {}

    if not os.path.exists(sources_path):
        raise FileNotFoundError(
            f"Missing {sources_path}. "
            "Create it using the cycle_sources.json template provided."
        )

    raw = json.load(open(sources_path, "r", encoding="utf-8"))
    if isinstance(raw, list):              # legacy flat array (oldest format)
        sources = raw
    else:
        sources = _collect_cycle_sources(raw, cycle_filter)
    out = []

    for s in sources:
        url   = s["url"].strip()
        label = s.get("label", "").strip()

        if not refresh and url in cache:
            out.append(cache[url])
            log("INFO", f"  [cached] {label or url}")
            continue

        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            snippet = strip_html(r.text)[:1500]
            item = {
                "label":        label,
                "url":          url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "date_hint":    _infer_date(snippet),
                "snippet":      snippet,
            }
            log("OK", f"  Fetched: {label or url}")
        except Exception as e:
            item = {
                "label":        label,
                "url":          url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "date_hint":    "Unknown",
                "snippet":      f"[FETCH_FAILED] {e}",
            }
            log("WARN", f"  Failed: {label or url} — {e}")

        cache[url] = item
        out.append(item)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    log("INFO", f"Cycle cache saved: {len(cache)} entries → {cache_path}")
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def extract_data_json(text: str) -> tuple[dict, str]:
    if "<DATA_JSON>" not in text:
        raise ValueError("Model did not return <DATA_JSON> opening tag.")

    if "</DATA_JSON>" not in text:
        log("WARN", "Missing </DATA_JSON> — attempting brace recovery ...")
        j_raw = text.split("<DATA_JSON>", 1)[1].strip()
        last_brace = j_raw.rfind("}")
        if last_brace == -1:
            raise ValueError("Cannot recover JSON: no closing brace found.")
        j_raw = j_raw[:last_brace + 1]
        md = "_Markdown unavailable: model output was truncated._"
    else:
        j_raw = text.split("<DATA_JSON>", 1)[1].split("</DATA_JSON>", 1)[0].strip()
        if "<MARKDOWN>" in text and "</MARKDOWN>" in text:
            md = text.split("<MARKDOWN>", 1)[1].split("</MARKDOWN>", 1)[0].strip()
        else:
            md = text.split("</DATA_JSON>", 1)[1].strip()

    parsed = json.loads(j_raw)
    if isinstance(parsed, list):
        raise ValueError("Model returned a JSON array instead of the schema object.")
    if not any(k in parsed for k in ("meta", "sectors", "tokens")):
        raise ValueError("Parsed JSON missing expected keys (meta/sectors/tokens).")
    return parsed, md

# ═══════════════════════════════════════════════════════════════════════════════
# POST-PROCESSING GATES  — correctness enforced in code, not just in prompt
# ═══════════════════════════════════════════════════════════════════════════════

def clamp_scores(data: dict) -> None:
    for s in data.get("sectors", []):
        try:
            s["score"] = max(0, min(100, int(float(s.get("score", 0)))))
        except Exception:
            s["score"] = 0
    for t in data.get("tokens", []):
        try:
            t["spike_score"] = max(0, min(100, int(float(t.get("spike_score", 0)))))
        except Exception:
            t["spike_score"] = 0

def normalize_list_fields(data: dict) -> None:
    """
    The model sometimes puts dicts into for/against/invalidations instead of strings.
    Convert any dict items to a readable string so the export never crashes.
    """
    def _coerce(val):
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return (val.get("title") or val.get("url") or
                    val.get("text") or val.get("claim") or str(val))
        return str(val)

    for s in data.get("sectors", []):
        for field in ("for", "against", "invalidations", "top_entities"):
            s[field] = [_coerce(v) for v in s.get(field, []) if v]

    for t in data.get("tokens", []):
        for field in ("catalysts", "traction", "tokenomics_risks",
                      "security", "liquidity", "invalidations"):
            t[field] = [_coerce(v) for v in t.get(field, []) if v]

def normalize_sectors(data: dict) -> None:
    """Remap any sector not in taxonomy to Other/Unknown."""
    for s in data.get("sectors", []):
        if s.get("sector") not in SECTOR_TAXONOMY:
            log("WARN", f"  Sector '{s.get('sector')}' not in taxonomy → Other/Unknown")
            s["sector"]     = "Other/Unknown"
            s["confidence"] = "Low"
            if s.get("status") == "Verified":
                s["status"] = "Speculative"
    for t in data.get("tokens", []):
        if t.get("sector") not in SECTOR_TAXONOMY:
            t["sector"] = "Other/Unknown"


def enforce_sector_gates(data: dict) -> None:
    """
    Reject sectors only if they have NO evidence at all.
    Downgrade (not reject) sectors with thin but non-zero evidence.
    """
    for s in data.get("sectors", []):
        has_for          = len(s.get("for", []))          >= 1
        has_against      = len(s.get("against", []))      >= 1
        has_invalidation = len(s.get("invalidations", [])) >= 1
        total_points     = sum([has_for, has_against, has_invalidation])

        if total_points == 0:
            # Truly empty — reject
            s["status"]     = "Rejected"
            s["score"]      = 0
            s["confidence"] = "Low"
        elif total_points == 1:
            # Only one field — downgrade but keep
            s["status"]     = "Rejected"
            s["score"]      = min(s.get("score", 0), 25)
            s["confidence"] = "Low"
        elif total_points == 2:
            # Thin but usable — cap score, mark Speculative
            s["status"]     = "Speculative"
            s["score"]      = min(s.get("score", 0), 50)
            s["confidence"] = "Low"
        # total_points == 3 → keep whatever the model assigned


def enforce_token_gates(data: dict, candidates: list[str],
                        strength: dict[str, int],
                        confidence_scores: dict[str, dict] | None = None) -> None:
    """
    Hard gate — runs after parsing, regardless of what the model said.
    Drops tokens that: are not in candidates / look like English words /
    have <2 mentions AND no primary non-Reddit source.
    Also enforces deterministic tier from confidence_scores when available.
    """
    cand_set = set(c.upper() for c in (candidates or []))
    kept = []
    for t in data.get("tokens", []):
        sym = (t.get("symbol") or "").upper().strip()
        if not sym:
            continue
        if sym not in cand_set:
            log("INFO", f"  Token '{sym}' dropped (not in candidates)")
            continue
        if looks_like_english_word(sym):
            log("INFO", f"  Token '{sym}' dropped (looks like English word)")
            continue
        mentions   = strength.get(sym, 0)
        primary_ok = has_non_reddit_source(t.get("sources", []))
        if mentions < 2 and not primary_ok:
            log("INFO", f"  Token '{sym}' dropped (mentions={mentions}, no primary source)")
            continue
        kept.append(t)
    # Enforce deterministic tier from confidence_scores
    for t in kept:
        sym = (t.get("symbol") or "").upper().strip()
        cs = (confidence_scores or {}).get(sym, {})
        if cs:
            t["tier"] = cs.get("tier") or _compute_tier(cs)
            if "explanation" not in t:
                t["explanation"] = cs.get("explanation", "")
        elif t.get("tier") not in ("investment_quality", "speculative"):
            t["tier"] = "speculative"
    data["tokens"] = kept[:10]


def _stamp_meta(data: dict, run_id: str, now: datetime,
                run_mode: str, time_window: str) -> None:
    data.setdefault("meta", {})
    data["meta"]["run_id"]       = run_id
    data["meta"]["generated_at"] = now.isoformat()
    data["meta"]["run_mode"]     = run_mode
    data["meta"]["time_window"]  = time_window
    data["meta"].setdefault("cycles", [])
    data["meta"].setdefault("regime",
        {"label": "Unknown", "confidence": "Low", "sources": []})


def _fallback_data(run_id: str, now: datetime,
                   run_mode: str, time_window: str) -> dict:
    return {
        "meta": {
            "run_id":       run_id,
            "generated_at": now.isoformat(),
            "run_mode":     run_mode,
            "time_window":  time_window,
            "cycles":       [],
            "regime": {"label": "Unknown", "confidence": "Low", "sources": []},
        },
        "sectors": [],
        "tokens":  [],
        "questions_for_user": [
            "Model did not return structured output. Check OLLAMA_MODEL and retry."
        ],
    }

# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════════════════════

def sheets_service(sa_key_path: str):
    creds = service_account.Credentials.from_service_account_file(
        sa_key_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def sheets_append(service, spreadsheet_id: str, tab: str,
                  rows: list[list]) -> None:
    body = {"values": rows}
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

# ═══════════════════════════════════════════════════════════════════════════════
# NOTION EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def notion_export(db_id: str, token: str, title: str, props: dict,
                  md: str, data: dict) -> None:
    notion    = NotionClient(auth=token)
    json_blob = json.dumps(data, ensure_ascii=False)

    page = notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name":       {"title": [{"text": {"content": title}}]},
            "RunDate":    {"date":  {"start": props["run_date"]}},
            "RunMode":    {"select": {"name": props["run_mode"]}},
            "TimeWindow": {"rich_text": [{"text": {"content": props["time_window"]}}]},
            "TopSectors": {"rich_text": [{"text": {"content": props["top_sectors"]}}]},
            "Confidence": {"select": {"name": props["confidence"]}},
            "JsonBlob":   {"rich_text": [{"text": {"content": json_blob[:2000]}}]},
        },
    )
    page_id = page["id"]

    def chunk(s, n=1800):
        for i in range(0, len(s), n):
            yield s[i: i + n]

    blocks = []
    for part in chunk(md):
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text",
                                         "text": {"content": part}}]},
        })
    blocks.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text",
                                     "text": {"content": "Full JSON Output"}}]},
    })
    for part in chunk(json.dumps(data, ensure_ascii=False, indent=2), 1800):
        blocks.append({
            "object": "block", "type": "code",
            "code": {
                "language": "json",
                "rich_text": [{"type": "text", "text": {"content": part}}],
            },
        })

    for i in range(0, len(blocks), 80):
        notion.blocks.children.append(
            block_id=page_id, children=blocks[i: i + 80]
        )

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    load_dotenv()
    tz = ZoneInfo(os.getenv("TIMEZONE", "Europe/Lisbon"))

    ap = argparse.ArgumentParser(description="Crypto Sector Cycle Radar")
    ap.add_argument("--run-mode", required=True,
                    choices=["DAILY_SCAN", "SECTOR_RANKING",
                             "TOKEN_SHORTLIST", "CYCLE_MAP_BUILD"])
    ap.add_argument("--hours",   type=int, default=24,
                    help="Evidence window in hours (Reddit modes only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip Sheets/Notion — print preview to terminal instead")
    ap.add_argument("--include-memes", action="store_true",
                    help="Override default meme post exclusion")
    ap.add_argument("--cycle-sources", default="cycle_sources.json",
                    help="Path to cycle sources JSON (CYCLE_MAP_BUILD only)")
    ap.add_argument("--cycle-cache",   default="cycle_sources_cache.json",
                    help="Path to cycle fetch cache")
    ap.add_argument("--refresh-cycle-sources", action="store_true",
                    help="Force re-fetch all cycle sources (ignore cache)")
    ap.add_argument("--cycle-phase",
                    choices=["accumulation", "bull", "peak", "bear", "recovery"],
                    default=None,
                    help="Override market cycle phase for source selection")
    ap.add_argument("--cycle",
                    choices=["2017_bull", "2020_defi", "2021_bull", "2022_bear", "2024_halving"],
                    default=None,
                    help="Filter CYCLE_MAP_BUILD to a specific named cycle")
    ap.add_argument("--discovery", action="store_true",
                    help="Enable non-Reddit discovery layer (TOKEN_SHORTLIST only)")
    ap.add_argument("--discovery-sources", default="discovery_sources.json",
                    help="Path to discovery sources JSON")
    ap.add_argument("--discovery-cache",   default="discovery_sources_cache.json",
                    help="Path to discovery fetch cache (currently unused — RSS is stateless)")
    ap.add_argument("--refresh-discovery", action="store_true",
                    help="Reserved for future discovery cache refresh")
    args = ap.parse_args()

    now    = datetime.now(tz)
    run_id = f"{args.run_mode}-{now.strftime('%Y%m%d-%H%M%S')}"
    model  = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")

    global _RUN_LOG_PATH
    _RUN_LOG_PATH = open_run_log(run_id, args.run_mode)

    log("INFO", f"Run started → {run_id}")
    log("INFO", f"Model       → {model}")
    if args.dry_run:
        log("WARN", "DRY RUN — Sheets/Notion export will be skipped")

    data: dict = {}
    md:   str  = ""

    # ─────────────────────────────────────────────────────────────────────────
    # CYCLE MAP BUILD
    # ─────────────────────────────────────────────────────────────────────────
    if args.run_mode == "CYCLE_MAP_BUILD":
        log("STEP", "Building cycle evidence pack ...")

        cycle_meta: dict | None = None
        if getattr(args, "cycle", None):
            _raw_cs = json.load(open(args.cycle_sources, "r", encoding="utf-8"))
            if isinstance(_raw_cs, dict):
                cycle_meta = _raw_cs.get("cycles", {}).get(args.cycle)
                if cycle_meta:
                    log("INFO", f"Cycle filter: {args.cycle} → {cycle_meta.get('label','')}")
                else:
                    log("WARN", f"Cycle '{args.cycle}' not found — using all sources")

        evidence = build_cycle_evidence(
            sources_path=args.cycle_sources,
            cache_path=args.cycle_cache,
            refresh=args.refresh_cycle_sources,
            cycle_filter=getattr(args, "cycle", None),
        )
        log("INFO", f"Evidence pack: {len(evidence)} sources ready")

        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                raw = call_ollama_cycle(model, evidence, cycle_meta=cycle_meta)
                print(f"\n{'─'*60}\n  OLLAMA RAW (attempt {attempt+1})\n{'─'*60}")
                print(raw[:5000])
                print(f"{'─'*60}\n")
                data, md = extract_data_json(raw)
                clamp_scores(data)
                normalize_list_fields(data)
                log("OK", f"Parsed: {len(data.get('sectors',[]))} sectors | "
                           f"{len(data.get('tokens',[]))} tokens")
                break
            except (ValueError, json.JSONDecodeError) as e:
                log("WARN", f"Attempt {attempt+1} failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    log("ERROR", "All retries exhausted — using fallback")
                    data = _fallback_data(run_id, now, args.run_mode, "historical")
                    md   = "_Model output could not be parsed._"

        _stamp_meta(data, run_id, now, args.run_mode, "historical")

    # ─────────────────────────────────────────────────────────────────────────
    # REDDIT MODES
    # ─────────────────────────────────────────────────────────────────────────
    else:
        since_utc   = (now - timedelta(hours=args.hours)).astimezone(timezone.utc)
        time_window = f"last {args.hours}h"
        log("INFO", f"Window: {time_window} | Since: {since_utc.strftime('%Y-%m-%d %H:%M UTC')}")

        cfg         = json.load(open("config.json", "r", encoding="utf-8"))

        # Apply limits from config
        limits = cfg.get("limits", {})
        if limits.get("max_posts_per_subreddit"):
            cfg["max_items_per_feed"] = limits["max_posts_per_subreddit"]
        cfg["_max_total_posts"] = limits.get("max_total_posts", 150)

        # Discovery layer setup
        use_disc = getattr(args, "discovery", False) and args.run_mode == "TOKEN_SHORTLIST"
        cfg["subreddits"] = load_subreddits_from_config(cfg, use_discovery=use_disc)

        discovery_items: list[dict] = []
        if use_disc:
            log("STEP", "Fetching non-Reddit discovery sources ...")
            discovery_items = fetch_discovery_rss_items(
                args.discovery_sources,
                max_per_feed=cfg.get("max_items_per_feed", 25),
                run_id=run_id,
                run_mode=args.run_mode,
            )

        # Load cycle sources for phase-aware subreddit selection
        _raw_cs = json.load(open(args.cycle_sources, "r", encoding="utf-8")) \
                  if os.path.exists(args.cycle_sources) else []
        cycle_data = _raw_cs if isinstance(_raw_cs, dict) else {"phases": {}, "legacy_cycle_evidence": _raw_cs}

        phase = resolve_cycle_phase(args, cfg)
        cfg   = {**cfg, "subreddits": resolve_phase_subreddits(phase, cycle_data, cfg["subreddits"])}
        if phase:
            log("INFO", f"Cycle phase: {phase} → using phase subreddits")

        ledger_path = os.getenv("LEDGER_PATH", "trend_ledger.jsonl")

        purge_old_ledger(ledger_path, keep_hours=72)

        log("STEP", "Starting Reddit RSS fetch ...")
        items = fetch_reddit_items(cfg, since_utc, run_id=run_id, run_mode=args.run_mode)
        log_step(_RUN_LOG_PATH, "reddit_fetch", item_count=len(items))
        append_ledger(ledger_path, run_id, items)
        ledger_recent = load_recent_ledger(ledger_path, since_utc, limit=250)
        log("INFO", f"Ledger loaded: {len(ledger_recent)} items in window")

        trimmed = trim_ledger_for_prompt(ledger_recent, max_items=20)
        log("INFO", f"Prompt ledger: {len(trimmed)} items after trim")

        # Enrich top 20 posts with full selftext
        log("STEP", "Enriching top 20 posts with Reddit selftext ...")
        rss_headers    = {"User-Agent": "crypto-radar/1.0 (rss trend miner)"}
        enriched_count = 0
        for it in trimmed[:30]:
            extra = enrich_reddit_post(it["url"], rss_headers)
            it["selftext"]     = extra["selftext"] or it.get("selftext", "")
            it["reddit_score"] = extra["reddit_score"] or 0
            it["num_comments"] = extra["num_comments"] or 0
            it["outbound_url"] = extra["outbound_url"] or ""
            it["engagement"]   = (it["reddit_score"] or 0) + 2 * (it["num_comments"] or 0)
            if extra["selftext"]:
                enriched_count += 1
        log("INFO", f"Enriched {enriched_count}/20 posts with selftext")

        # NOW filter zero-engagement and re-sort by engagement descending
        before_filter = len(trimmed)
        trimmed = [it for it in trimmed if it["engagement"] > 0]
        trimmed.sort(key=lambda x: x["engagement"], reverse=True)
        log("INFO", f"Engagement filter: {before_filter} → {len(trimmed)} posts (sorted by engagement)")
        log_step(_RUN_LOG_PATH, "engagement_filter", before=before_filter, kept=len(trimmed))

        # Meme filter
        if not args.include_memes:
            before  = len(trimmed)
            trimmed = filter_memes(trimmed)
            log("INFO", f"Meme filter: {before} → {len(trimmed)} items")
            log_step(_RUN_LOG_PATH, "meme_filter", before=before, kept=len(trimmed))

        # Sector pre-filter
        trimmed, sector_stats = filter_no_sector(trimmed)
        log("INFO", f"Sector pre-filter: {sector_stats['discarded']} discarded, "
                    f"kept per sector: {sector_stats['kept_per_sector']}")
        log_step(_RUN_LOG_PATH, "sector_prefilter", **sector_stats)

        # Token candidates
        token_candidates  = extract_token_candidates(trimmed)
        if use_disc and discovery_items:
            disc_cands = extract_token_candidates(discovery_items)
            token_candidates = list(dict.fromkeys(token_candidates + disc_cands))
            log("INFO", f"Discovery added {len(disc_cands)} candidates; total: {len(token_candidates)}")
        strength          = candidate_strength(trimmed, token_candidates)
        strong_candidates = [c for c in token_candidates if strength.get(c, 0) >= 1]
        confidence_scores = token_confidence_score(
            strong_candidates, trimmed,
            discovery_items=discovery_items if use_disc else None,
        )
        log("INFO",
            f"Token candidates ({len(strong_candidates)}): {strong_candidates[:20]}"
            f"{'...' if len(strong_candidates) > 20 else ''}")
        log("INFO", f"Mention ≥2: { {k:v for k,v in strength.items() if v>=2} }")
        log("INFO", f"Confidence scores: { {k:v['confidence'] for k,v in confidence_scores.items()} }")

        MAX_RETRIES = 3

        # ── TOKEN_SHORTLIST — 2-pass pipeline ────────────────────────────────
        if args.run_mode == "TOKEN_SHORTLIST":

            # Pass 1: sector ranking
            d1, md1 = None, ""
            for attempt in range(MAX_RETRIES):
                try:
                    raw1 = call_ollama_sectors(model, trimmed)
                    print(f"\n{'─'*60}\n  OLLAMA RAW — SECTORS (attempt {attempt+1})\n{'─'*60}")
                    print(raw1[:3000])
                    print(f"{'─'*60}\n")
                    d1, md1 = extract_data_json(raw1)
                    clamp_scores(d1)
                    normalize_list_fields(d1)
                    normalize_sectors(d1)
                    enforce_sector_gates(d1)
                    log("OK", f"Sectors pass: {len(d1.get('sectors',[]))} sectors")
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    log("WARN", f"Sectors attempt {attempt+1} failed: {e}")
                    if attempt == MAX_RETRIES - 1:
                        d1  = _fallback_data(run_id, now, args.run_mode, time_window)
                        md1 = "_Sector pass failed._"

            # Derive focus sectors from top non-rejected results
            ranked = sorted(
                d1.get("sectors", []),
                key=lambda x: x.get("score", 0), reverse=True
            )
            focus_sectors = [
                s.get("sector") for s in ranked
                if s.get("status") != "Rejected"
            ][:2] or ["Other/Unknown"]
            log("INFO", f"Token focus sectors: {focus_sectors}")

            # Pass 2: token shortlist inside focus sectors
            d2, md2 = None, ""
            for attempt in range(MAX_RETRIES):
                try:
                    raw2 = call_ollama_tokens(
                        model, trimmed, focus_sectors,
                        strong_candidates, strength,
                        confidence_scores,
                        discovery_snippets=discovery_items if use_disc else None,
                    )
                    print(f"\n{'─'*60}\n  OLLAMA RAW — TOKENS (attempt {attempt+1})\n{'─'*60}")
                    print(raw2[:3000])
                    print(f"{'─'*60}\n")
                    d2, md2 = extract_data_json(raw2)
                    clamp_scores(d2)
                    normalize_list_fields(d2)
                    normalize_sectors(d2)
                    enforce_token_gates(d2, strong_candidates, strength,
                                        confidence_scores=confidence_scores)
                    log("OK", f"Tokens pass: {len(d2.get('tokens',[]))} tokens kept")
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    log("WARN", f"Tokens attempt {attempt+1} failed: {e}")
                    if attempt == MAX_RETRIES - 1:
                        d2  = _fallback_data(run_id, now, args.run_mode, time_window)
                        md2 = "_Token pass failed._"

            # Wire subreddit proposals
            proposals = generate_subreddit_proposals(d2.pop("subreddit_proposals", []), cfg)
            d2["subreddit_proposals"] = proposals
            if proposals["add"] or proposals["remove"]:
                log("WARN", f"Subreddit proposals (review manually): "
                            f"+{len(proposals['add'])} add, -{len(proposals['remove'])} remove")

            # Merge both passes
            data = {
                "meta":    d1.get("meta", {}),
                "sectors": ranked[:6],
                "tokens":  d2.get("tokens", [])[:10],
                "subreddit_proposals": proposals,
                "questions_for_user": (
                    d1.get("questions_for_user", []) +
                    d2.get("questions_for_user", [])
                )[:5],
            }
            md = (md1 + "\n\n---\n\n" + md2).strip()

        # ── DAILY_SCAN / SECTOR_RANKING — sectors only ────────────────────────
        else:
            for attempt in range(MAX_RETRIES):
                try:
                    raw = call_ollama_sectors(model, trimmed)
                    print(f"\n{'─'*60}\n  OLLAMA RAW (attempt {attempt+1})\n{'─'*60}")
                    print(raw[:5000])
                    print(f"{'─'*60}\n")
                    data, md = extract_data_json(raw)
                    clamp_scores(data)
                    normalize_list_fields(data)
                    normalize_sectors(data)
                    enforce_sector_gates(data)
                    log("OK", f"Parsed: {len(data.get('sectors',[]))} sectors | "
                               f"{len(data.get('tokens',[]))} tokens")
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    log("WARN", f"Attempt {attempt+1} failed: {e}")
                    if attempt == MAX_RETRIES - 1:
                        log("ERROR", "All retries exhausted — using fallback")
                        data = _fallback_data(run_id, now, args.run_mode, time_window)
                        md   = "_Model output could not be parsed._"

        _stamp_meta(data, run_id, now, args.run_mode, time_window)

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD EXPORT ROWS
    # ─────────────────────────────────────────────────────────────────────────
    gen_at = data["meta"]["generated_at"]
    tw     = data["meta"]["time_window"]

    sector_rows = []
    for s in data.get("sectors", [])[:6]:
        sector_rows.append([
            run_id, gen_at, tw,
            s.get("sector", ""),
            s.get("score", 0),
            s.get("confidence", "Low"),
            s.get("status", "Speculative"),
            s.get("narrative", ""),
            "; ".join(s.get("for", [])[:5]),
            "; ".join(s.get("against", [])[:5]),
            "; ".join(s.get("invalidations", [])[:5]),
            ", ".join(s.get("top_entities", [])[:10]),
        ])

    token_rows = []
    for t in data.get("tokens", [])[:10]:
        token_rows.append([
            run_id, gen_at,
            t.get("sector", ""),
            t.get("symbol", ""),
            t.get("name", "Unknown"),
            t.get("chain", "Unknown"),
            t.get("spike_score", 0),
            t.get("confidence", "Low"),
            t.get("tier", "speculative"),
            t.get("status", "Speculative"),
            t.get("thesis", ""),
            "; ".join(t.get("catalysts", [])[:5]),
            "; ".join(t.get("invalidations", [])[:5]),
        ])

    # ─────────────────────────────────────────────────────────────────────────
    # DRY RUN PREVIEW
    # ─────────────────────────────────────────────────────────────────────────
    if args.dry_run:
        log("INFO", f"[DRY RUN] {len(sector_rows)} sector rows | {len(token_rows)} token rows")
        print("\n" + "═"*60)
        print("  JSON PREVIEW (first 5000 chars)")
        print("═"*60)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
        print("\n" + "═"*60)
        print("  MARKDOWN PREVIEW")
        print("═"*60)
        print(md[:2000])
        log("OK", f"Dry run complete → {run_id}")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # GOOGLE SHEETS EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    log("STEP", "Exporting to Google Sheets ...")
    svc = sheets_service(os.getenv("GSHEETS_SA_KEY"))
    sid = os.getenv("GSHEETS_SPREADSHEET_ID")

    if sector_rows:
        sheets_append(svc, sid, "sectors", sector_rows)
        log("OK", f"Sheets: wrote {len(sector_rows)} sector rows")
    if token_rows:
        sheets_append(svc, sid, "tokens", token_rows)
        log("OK", f"Sheets: wrote {len(token_rows)} token rows")
    if not sector_rows and not token_rows:
        log("WARN", "Sheets: nothing to write (empty sectors and tokens)")

    # ─────────────────────────────────────────────────────────────────────────
    # NOTION EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    log("STEP", "Exporting to Notion ...")
    top_sectors = ", ".join(
        [s.get("sector", "") for s in data.get("sectors", [])[:6]]
    )
    confidence = (data.get("sectors") or [{}])[0].get("confidence", "Low")

    notion_export(
        db_id=os.getenv("NOTION_DATABASE_ID"),
        token=os.getenv("NOTION_TOKEN"),
        title=f"{args.run_mode} – {now.strftime('%Y-%m-%d')}",
        props={
            "run_date":    now.date().isoformat(),
            "run_mode":    args.run_mode,
            "time_window": tw,
            "top_sectors": top_sectors[:200],
            "confidence":  confidence,
        },
        md=md,
        data=data,
    )
    log("OK", "Notion page created (full JSON as code blocks)")
    log_step(_RUN_LOG_PATH, "run_complete", run_id=run_id)
    log("OK", f"Run complete → {run_id}")


if __name__ == "__main__":
    main()
