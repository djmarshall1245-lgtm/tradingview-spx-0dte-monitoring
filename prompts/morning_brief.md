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

⓪ OVERNIGHT TELLS — already in run.py --brief output. The pre-open global
   tape: US futures (/ES /NQ), VIX, 10Y, DXY, USD/JPY, oil, copper, gold,
   bitcoin, Nikkei, KOSPI, DAX — each with overnight % and a risk-on/off
   tally. Paste it here and add ONE line of interpretation:
   - Are Asia/Europe + futures pointing the same way (clean lean) or
     fighting each other (chop risk)?
   - Any single tell screaming (KOSPI -10% = chip rout; USD/JPY gapping =
     risk-off; VIX spiking)? Flag it.
   - Is /ES HOLDING or FADING the overnight move? Gaps fade — don't assume
     the overnight direction sticks into the open.
   NOT a trade trigger — context that frames the macro regime.

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

⑤ FLOW CONTEXT — your job, via UNUSUAL WHALES MCP.

   STALENESS DISCIPLINE (mandatory — applies to every UW call):

   FLOW DATA goes stale the moment a session ends. If the market hasn't
   opened today, DO NOT decompose/present it as if it were today's flow:
   - get_market_state (P/C, call/put premium): pre-open / weekend / holiday
     -> write: "NO LIVE FLOW — awaiting open." That's the whole section.
     Do not pull last session's numbers and dress them up in tables.
   - get_dark_pool_trades: pre-open -> ONE LINE max:
     "Last major prints were <date> at <level> — not actionable today."
     No tables. No "biggest blocks" decomposition.
   - market tide: pre-open -> ONE LINE max:
     "Prior session was call/put dominant" — no per-hour decomposition,
     no bullish/bearish conclusions drawn from yesterday's tide.

   POSITIONAL DATA is "state as of last close" — that IS the freshest
   available. Tag [CURRENT as of <last close date>], not [STALE]:
   - get_max_pain for FORWARD expiries (expiry > today): still current,
     dealers are still pinned to those strikes. Present normally.
   - get_greek_exposure_by_strike: current state of dealer positioning.
     Present normally.
   - get_open_interest_changes: current OI state. Present normally.

   INTRADAY (market open + > 15 min in): pull all freely, tag [TOOL].

   Per held position (and watchlist names with a forming setup), call the
   UW tools above. Phrase as conditions, not trade calls. NEVER fill a UW
   gap with general-knowledge color from training data — that's the
   fabrication failure RULE 3 forbids.

⑥ SUMMARY:
   - Macro regime + score (one line)
   - Positions that need eyes today (target/stop near, IV change, news flag)
   - Watchlist names with a setup forming (flow + news aligned).
     For each: ALSO check watchlists/leopold_holdings.yaml — if the name
     appears in that file (or its sector matches a top Leopold theme like
     AI power / data centers / chips), note "✓ Leopold position" or
     "✓ Leopold theme". This is a SMART-MONEY CONFIRMS flag — 45-day
     lagged 13F context, NOT a trade trigger. Trade desk gates still apply.
   - End with: "No trade calls — that's the trade desk's job, with your GO."

⑦ DO NOT TRADE UNTIL YOU VERIFY (MANDATORY — never skip):
   Produce a table listing EVERY claim above tagged [MEMORY], [STALE], or
   [NO DATA]. For each: (a) the claim, (b) the tag, (c) how to verify it
   pre-open. If this section is empty, you must explicitly write:
   "All facts above are [TOOL]-sourced this session — nothing to verify."
   Brief is INCOMPLETE without this section. Do not finalize without it.

⑧ TOOL RECEIPT (MANDATORY — output is INVALID without this):
   Required tools for this task (from SKILL.md frontmatter):
     - run.py (python, terminal-side)
     - firecrawl  (per-name news enrichment)
     - unusualwhales  (flow + max pain + GEX + dark pool)
   Produce a receipt for EACH:
     ✅ CALLED <tool> at <approx time>: <evidence — actual value, URL, or
        verbatim snippet pulled. Not "I called it" — show the FRUIT.>
     ❌ NOT CALLED <tool>: required but skipped. THIS VOIDS THE OUTPUT.
        Halt, tell me, do not ship a partial brief tagged as complete.
     ➖ N/A <tool>: explicitly say WHY the tool was not needed for THIS
        specific brief (e.g. "no positions, no per-name news for held").
        Vague reasons = failure.

   ANTI-DRIFT RULE (Karpathy discipline): you are FORBIDDEN from
   substituting one tool with another (web_search instead of Firecrawl,
   memory instead of UW). Each required tool is called by name or the
   output is voided. No "I'll use my training instead." No "let me
   summarize from what I know." If a tool isn't available, halt; do not
   work around it.
```
