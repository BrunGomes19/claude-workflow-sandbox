# Cycle Sources Checklist

Sources marked `"fetchable": false` or `"fetchable": null` in `cycle_sources.json` cannot be
auto-fetched by `build_cycle_evidence()`. This file tracks them, explains why, and provides
workarounds so their context is not lost.

**Workaround (all sources below):** Copy the key insight text into the `why_included` field
(max 300 chars). This text is visible to the LLM prompt builder as metadata even when the
page itself cannot be fetched.

---

## fetchable: false — JS-rendered SPAs

These URLs return a JavaScript shell with no useful HTML content for a plain HTTP GET.

### BlackRock iShares Bitcoin ETF (IBIT)
- **URL:** `https://www.blackrock.com/us/individual/products/333011/`
- **Category:** macro
- **Reason:** Single-page application (React); HTML body is empty without JS execution.
- **Workaround:** Key data (AUM, net inflows, inception date) available via Bloomberg terminal,
  iShares daily CSV downloads, or SEC N-CEN filings. Copy key AUM/flow stats into `why_included`.
- **Manual test:** `curl -s "https://www.blackrock.com/us/individual/products/333011/" | grep -c "script"`
  — high script count, near-zero text content confirms JS-only rendering.

### Glassnode: MVRV-Z Score
- **URL:** `https://studio.glassnode.com/metrics?a=BTC&m=market.MvrvZScore`
- **Category:** bitcoin_onchain
- **Reason:** Glassnode Studio requires authentication; unauthenticated GET returns login redirect.
- **Workaround:** Historical MVRV-Z values documented in public Glassnode blog posts and
  LookIntoBitcoin. Copy current Z-score range into `why_included`.
- **Manual test:** `curl -s "https://studio.glassnode.com/metrics?a=BTC&m=market.MvrvZScore" | grep -c "login"`

### Glassnode: Exchange Net Position Change
- **URL:** `https://studio.glassnode.com/metrics?a=BTC&m=distribution.BalanceExchangesNetChange`
- **Category:** bitcoin_onchain
- **Reason:** Same auth wall as all Glassnode Studio URLs.
- **Workaround:** Exchange flow data available in Glassnode weekly reports (free tier) and
  CryptoQuant public charts. Copy current flow direction into `why_included`.
- **Manual test:** `curl -s "https://studio.glassnode.com/metrics?a=BTC&m=distribution.BalanceExchangesNetChange" | grep -c "login"`

### LookIntoBitcoin: Pi Cycle Top Indicator
- **URL:** `https://www.lookintobitcoin.com/charts/pi-cycle-top-indicator/`
- **Category:** bitcoin_onchain
- **Reason:** Chart data rendered via JavaScript; static HTML has no meaningful content.
- **Workaround:** Current Pi Cycle status (crossed/not crossed) is widely reported in crypto
  media. Copy status and MA values into `why_included`.
- **Manual test:** `curl -s "https://www.lookintobitcoin.com/charts/pi-cycle-top-indicator/" | grep -c "<canvas"`

### DeFiLlama: TVL charts by chain
- **URL:** `https://defillama.com/chains`
- **Category:** sector_analysis
- **Reason:** React SPA; all TVL data loaded via API calls after initial JS execution.
- **Workaround:** Use DeFiLlama's public API directly:
  `https://api.llama.fi/v2/chains` returns JSON with current TVL per chain.
  Copy top-5 chains by TVL into `why_included`.
- **Manual test:** `curl -s "https://api.llama.fi/v2/chains" | python -m json.tool | head -40`

---

## fetchable: false — Paywalled / Auth Required

### Messari: 2021 Crypto Theses
- **URL:** `https://messari.io/report/crypto-theses-for-2021`
- **Category:** sector_analysis
- **Reason:** Messari Pro report; unauthenticated access returns a paywall gate page.
- **Workaround:** Key theses from this report were widely quoted and summarised in public
  crypto media (The Block, Decrypt, CoinDesk). Copy the top 3 sector narratives into
  `why_included` from public summaries.
- **Manual test:** `curl -s "https://messari.io/report/crypto-theses-for-2021" | grep -i "paywall\|subscribe\|login"`

---

## fetchable: null — Untested

### CoinGecko: 2024 Annual Crypto Report
- **URL:** `https://www.coingecko.com/research/publications/2024-annual-crypto-report`
- **Category:** sector_analysis
- **Status:** Not yet tested. CoinGecko research pages vary — some are plain HTML PDFs,
  others are gated.
- **Manual test:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}" \
    "https://www.coingecko.com/research/publications/2024-annual-crypto-report"
  ```
  - `200` with text/html → likely fetchable, update to `"fetchable": true`
  - `200` with PDF content-type → download PDF, extract key stats, update `why_included`
  - `403` / redirect to login → update to `"fetchable": false`

---

## Verification Summary

After manual testing each source, update `cycle_sources.json` accordingly:

| Source | Current | Action if fetchable | Action if not fetchable |
|--------|---------|---------------------|------------------------|
| BlackRock IBIT | `false` | Change to `true` | Keep `false`, update `why_included` with AUM |
| Glassnode MVRV-Z | `false` | Change to `true` | Keep `false`, add current Z-score value |
| Glassnode Exchange Flows | `false` | Change to `true` | Keep `false`, add flow direction |
| LookIntoBitcoin Pi Cycle | `false` | Change to `true` | Keep `false`, add MA crossover status |
| DeFiLlama TVL | `false` | Change to `true` | Keep `false`, use API workaround |
| Messari 2021 Theses | `false` | Change to `true` | Keep `false`, add top-3 theses text |
| CoinGecko 2024 Report | `null` | Change to `true` | Change to `false`, update `why_included` |
