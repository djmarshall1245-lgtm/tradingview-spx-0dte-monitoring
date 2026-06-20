---
name: morning-brief
description: Daily pre-open monitor — macro score, book health, alerts, per-name news + flow
version: 1.0.0
metadata:
  hermes:
    tags: [trading, monitor, premarket, observe]
    category: trading
    requires_tools: [unusualwhales, firecrawl]
---

# Morning Brief — daily monitor (OBSERVE layer, never trades)

Run pre-open. Combines the deterministic Python skeleton (macro / book / alerts)
with Claude Code's MCP tools (Firecrawl for news, UW for flow). Reports
CONDITIONS and FACTS — never buy/sell.

Two-step flow:
  1. In terminal:  `python run.py --brief`   ← prints macro/book/alerts/headlines
  2. Then paste the block below into Claude Code so Claude enriches the
     headlines via Firecrawl and pulls flow context via UW.

---

```
Give me my morning brief.

STEP 0 — READ THE YAML FIRST: read strategy/strategy.yaml, strategy/goal.yaml,
and config.yaml watchlist before anything. Files are the source of truth — if
a recap disagrees with disk, THE FILE WINS.

Then read my data:
  • run.py --brief output (paste below, or just run it yourself)
  • config.yaml watchlist + positions.yaml positions
  • data/monitor.db for stored snapshots / valuations

Tag every fact [TOOL]/[STALE]/[MEMORY]. Show source URLs for news.
Re-pull live; never reuse cached files for today's numbers.

═══════════════════════════════════════════════════════════════════════
ANTI-FABRICATION RULES — read before writing a single number
═══════════════════════════════════════════════════════════════════════

RULE 1 — SOURCE OR OMIT. Any number you write (price, %, P/E, EPS, YTD,
revenue, target, calendar date) MUST be one of:
  (a) [TOOL] with the source URL AND a quoted snippet from the actual page,
      OR
  (b) [NO DATA] — say so explicitly. Do NOT fill from memory to keep the
      brief looking complete.
A [TOOL] tag without a URL and a verbatim snippet is a bug. Fabrication
of a single number invalidates the whole brief and is the worst possible
failure mode (per CLAUDE.md trading-safety rules).

RULE 2 — SANITY-CHECK BEFORE POSTING. Before you submit each section,
self-verify:
  - Day-of-week matches the date (e.g. 2026-06-25 is a Thursday, not Wed).
  - P/E × EPS ≈ price (catches phantom price/multiple math).
  - YTD% × start-of-year price ≈ current price.
  - Any "up X% since Y" claim has a verifiable Y price.
If a check fails, the number is wrong — don't post it; mark [NO DATA].

RULE 3 — FIRECRAWL DISCIPLINE. One Firecrawl call per name; if it returns
nothing material, the per-name news block for that ticker is:
   "<TICKER>: [NO DATA] (Firecrawl returned no material story today)."
Do NOT pad with general-knowledge color about the company. The whole point
of Firecrawl is sourced specificity. No source = no claim.

RULE 4 — UW STALENESS. If today is a weekend or holiday, UW data is from
the last trading day. Tag every UW number [STALE <date>]. Do not present
stale data as if it were today's flow.

═══════════════════════════════════════════════════════════════════════

① MACRO SCORE — already in run.py --brief output. Just paste it here.
   0-100 deterministic score from VIX + term structure + breadth + credit.
   NOT a trade trigger; it tags the regime the book sits in.

② BOOK HEALTH — already in run.py --brief. Per position: mark, P&L, DTE,
   delta, theta/day, IV rank (from my own snapshots), progress to MY target /
   MY stop. Aggregate Greeks and concentration flags.

③ CONDITION ALERTS — already in run.py --brief. Facts, never instructions.
   Phrase like "NOK calls hit your target level."

④ PER-NAME NEWS — your job. For each name in my watchlist + positions:
   - Read the raw headlines from run.py --brief output.
   - Use FIRECRAWL MCP to pull the full text of the most material 1-2 stories.
     Prefer the FREE SOURCES in config.yaml → news.free_sources
     (Reuters, AP, CNBC, MarketWatch, Yahoo Finance, FRED, SEC EDGAR,
     Cboe, MarketChameleon, CME FedWatch, investing.com calendar).
     Cite the URL each time.
   - Return: 2-sentence summary, sentiment (positive/neutral/negative),
     key drivers, and a flag if anything materially hits an open position.
   - NEVER say buy or sell. Summarize only.

⑤ FLOW CONTEXT — your job, via UNUSUAL WHALES MCP:
   For each held position (and any name on my watchlist that has a hot setup):
   - get_market_state for the current regime read
   - get_greek_exposure_by_strike for GEX walls near the strike
   - get_dark_pool_trades for biggest prints + lean
   - get_max_pain to see where dealers are pinned
   Phrase as conditions, not calls.

⑥ SUMMARY:
   - Macro regime + score (one line)
   - Positions that need eyes today (target/stop near, IV change, news flag)
   - Watchlist names with a setup forming (flow + news aligned)
   - End with: "No trade calls — that's the trade desk's job, with your GO."

⑦ DO NOT TRADE UNTIL YOU VERIFY (MANDATORY — never skip):
   Produce a table listing EVERY claim above tagged [MEMORY], [STALE], or
   [NO DATA]. For each: (a) the claim, (b) the tag, (c) how to verify it
   pre-open. If this section is empty, you must explicitly write:
   "All facts above are [TOOL]-sourced this session — nothing to verify."
   Brief is INCOMPLETE without this section. Do not finalize without it.
```
