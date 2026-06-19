# Morning Brief — daily monitor (OBSERVE layer, never trades)

Run pre-open. Combines your existing SPX brief discipline with AI Pathways'
per-name news + macro score. Reports CONDITIONS and FACTS — never buy/sell.

Two ways to run:
  • Manual: paste the block below into terminal Claude Code.
  • Automated: `python run.py --brief` (uses lib/ + data/monitor.db). See README.

---

```
Give me my morning brief. Tag every fact [TOOL]/[STALE]/[MEMORY]. Show source
URLs for news. Re-pull live; never reuse a cached file for today's numbers.

① MACRO SCORE (deterministic, 0-100) — from lib/macro_gate.py:
   VIX level + 1yr percentile · VIX/VIX3M term structure · breadth (%SPY
   above 200d MA) · credit (HYG-TLT). Same data in, same score out.
   -> One number + the regime it implies. NOT a trade trigger.

② BOOK HEALTH (if I hold anything) — from lib/snapshot.py / monitor.db:
   Per position: mark, value, $/% P&L, DTE, delta, theta/day, vega, IV,
   IV rank (from my own snapshots), progress to MY target / MY stop.
   Aggregate: net delta, total daily theta bleed, net vega, allocation by
   ticker & sector + concentration flags (>40% ticker / >60% sector).

③ CONDITION ALERTS (facts, never instructions) — from lib/alerts.py:
   target_hit · stop_hit · target_near (80%) · iv_change (>=20%) ·
   new_strikes · new_expiry. Phrase like "NOK calls hit your target level."

④ PER-NAME NEWS (the one paid piece) — from lib/news.py, cached per day:
   For each held name: 3-day headline summary, sentiment, key drivers, and a
   flag for anything that hits my position. Claude summarizes — never says
   buy/sell. Show source URLs.

⑤ SUMMARY: macro regime + which positions need eyes today. No trade calls —
   that's the trade desk's job, with my GO.
```
