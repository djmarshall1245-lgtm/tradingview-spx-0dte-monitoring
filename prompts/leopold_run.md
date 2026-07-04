---
name: leopold-run
description: Smart-money sweep of the Leopold Aschenbrenner 13F book — live quotes, flow check, theme heat, confirms/diverges vs my desk
version: 1.0.0
metadata:
  hermes:
    tags: [trading, smart-money, 13f, leopold, watchlist, observe]
    category: trading
    requires_tools: [alpaca, unusualwhales, firecrawl]
---

# Leopold Run — smart-money sweep (OBSERVE layer, never trades)

Sweeps `watchlists/leopold_holdings.yaml` (Situational Awareness LP, Q1 2026
13F) against the live tape: how the book is trading TODAY, whether options
flow agrees with his positioning, and whether any of it confirms or diverges
from what MY desk is watching. Reports facts — never buy/sell.

Run it when: a Leopold name shows up in my scans, the AI power/data-center
theme is moving, or as a weekly theme pulse. NOT part of the daily brief —
this is an on-demand layer.

Standing caveat baked into every output: the 13F is a snapshot of
2026-03-31 filed 2026-05-15 — a 45-day-lagged photo of a fund with 63.5%
turnover. He may have exited anything. Next 13F ~Fri 2026-08-14.

---

```
Run my Leopold sweep.

STEP 0 — ANCHOR: run `date` and state "Today is <weekday> <YYYY-MM-DD>."
Then read watchlists/leopold_holdings.yaml — it is the roster for this run.
Tag every fact [TOOL]/[STALE]/[MEMORY]. The 13F data itself is ALWAYS
[STALE — filed 2026-05-15, positions as of 2026-03-31]; say so up top.

STEP 1 — LIVE TAPE ON THE BOOK               [TOOL] Alpaca (stocks lane)
Pull live snapshots for the TOP-10 longs by weight:
  BE, SNDK, CRWV, IREN, CORZ, APLD, RIOT, CLSK, SEI, TE
Table: ticker | last | day % | vs prior close | 13F weight % | q1_change.
Flag anything moving ±3%+ today. Note: these are stocks/ETFs — Alpaca's
lane; feed is IEX, fine for snapshots.

STEP 2 — THEME HEAT READ
One line per theme, computed from Step 1: AI power (BE, TE) · data
center/mining (IREN, CORZ, APLD, RIOT, CLSK) · storage/memory (SNDK) ·
AI cloud (CRWV). Is the Leopold THEME green, red, or mixed today?

STEP 3 — PUT-HEDGE SANITY                    [TOOL] Alpaca
He is short via puts: SMH, NVDA, ORCL, AVGO (+AMD hedged both ways).
Pull those 4 quotes. If his LONGS are up and his HEDGE names are down,
the whole book is working; if both are up, the hedge is bleeding — say
which state we're in today.

STEP 4 — FLOW CHECK ON MOVERS                [TOOL] Unusual Whales
For (only) the names that flagged ±3%+ in Step 1, max 4 names: net options
flow lean (calls vs puts) + any unusual activity. Does today's
institutional flow AGREE with Leopold's positioning in that name, or is
smart money exiting? Verdict per name: FLOW CONFIRMS / FLOW FADES / QUIET.

STEP 5 — NEWS ON THE HOTTEST NAME            [TOOL] Firecrawl (URLs required)
For the single biggest mover only: 2-3 headlines with source URLs. No
link = [MEMORY], not fact.

STEP 6 — CONFIRMS / DIVERGES vs MY DESK
Cross-check against config.yaml watchlist + positions.yaml:
  - Any of my watchlist names in his book (long or put-hedged)? AMD is on
    BOTH of our lists — and he holds it long AND puts (hedged); NVDA is my
    watchlist but his PUT. Call these out explicitly.
  - One-line verdict: does today's Leopold tape CONFIRM, CONTRADICT, or
    say NOTHING about my current bias?

STEP 7 — DO NOT TRADE UNTIL YOU VERIFY
List every [MEMORY]/[STALE] claim + how to verify. Always include:
  - "CRWV = CoreWeave vs CrowdStrike ambiguity in the yaml — verify before
    acting on that name" (the file itself flags it; CrowdStrike is CRWD).
  - "All weights/positions are the 2026-03-31 snapshot — 63.5% turnover
    fund; he may be out."

RULES: numbers from tools = trust; stories = verify. This is OBSERVE only —
no trade calls, no sizing. If a tool fails, say MISSING; never fill from
memory. Keep the whole output under ~60 lines.
```
