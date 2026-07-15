# Daily routine — the desk day, start to finish

Claude: when the user asks "what's my routine", "what's next today", or starts
a session with no specific ask during market hours, walk this file. The times
are ET. Numbers (cap, band, stop) always come from `strategy/strategy.yaml` +
`strategy/goal.yaml` — this file holds the SEQUENCE, never the values.
If the user says their routine changed, update THIS file (the file wins).

## Pre-market (before 9:30)
1. Mac terminal: `cd ~/tradingview-spx-0dte-monitoring && git pull origin claude/plce-XFleD`
2. `python3 run.py --brief` — prints today_cap, overnight tells, freshness.
3. Start Claude → `/mcp` → all 6 servers connected (tradingview, unusualwhales,
   firecrawl, robinhood-trading, FMP, alpaca). Any missing = HALT per CLAUDE.md.
4. Trigger the morning brief: "Give me my SPX 0DTE morning brief — pull my JC
   levels, institutional flow, and today's news + economic calendar with
   source links. Tag every fact [TOOL]/[STALE]/[MEMORY]."
5. If price gapped overnight: update Voodoo inputs (R3..S3) on the chart
   BEFORE the open — stale levels = wrong targets.

## Trading window (9:45–14:30, skip 12:00–13:00 lunch)
- No entries before 9:45. No entries during lunch. None after 14:30.
- When a signal sets up (1-2x/day max): run the trade desk — CALL or PUT
  prompt (quant → flow → tape integrity → decision gate).
- Cap = today_cap from the brief (funded cap; currently 1/day at $794).
  Two losses = done for the day, regardless of cap.
- Every order: review preview → user's manual GO → place. Limit at mid,
  never market. No blind retries — on an unclear order status, check
  get_option_orders, then halt and verify in the RH app.
- In a trade: manage per the relay protocol (MANAGE CHECK) — TP at next
  Voodoo, hard stop per strategy.yaml (currently −40%), exit on chart
  invalidation.

## Close (14:30–16:00)
- 14:30 → no new entries; manage only.
- 15:30 → force-close anything still open. 0DTE is never held past this.
- Log the trade in `journal/trades.jsonl` (or log the no-trade day —
  a correctly-gated flat day is a WIN, not a miss).

## Evening (any time after close)
1. `python3 run.py --supervise` — manual audit (MiniMax second-model check).
   NEVER scheduled. Read the memo; disagreements are Friday-loop input.
2. Commit + push journal/audit updates so the cloud session sees them.

## Friday only (after close)
- Run the Friday loop (`prompts/friday_loop.md`): review the week vs
  goal.yaml, adopt AT MOST one variable change, with explicit user GO.
- Current queue: see `scratch/quant_research_findings_2026-07-12.md`
  (Candidates A, D) + latest `journal/audits/` owner dispositions.

## Weekly anchors (2026-07 — prune when stale)
- Thu 2026-07-16: Kuva tender expiration — flip `tender_outcome` in
  goal.yaml when the result is known; never guess it.
- Fri 2026-07-17: first Friday loop of the live desk.
