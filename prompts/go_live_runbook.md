# GO-LIVE RUNBOOK — first real-money day (written for Mon 2026-07-13)

The seat manual for a live trading day. Written at the desk's go-live under
partial funding; every number here is a POINTER to strategy.yaml / goal.yaml
— if this doc and those files ever disagree, THE FILE WINS. Re-read them at
the top of every session; do not trust this prose or any recap over disk.

Standing identity of the desk: Claude proposes CONDITIONS, the user is the
GO — twice (trade GO, then order GO). Nothing auto-fires. Ever.

## A. PRE-FLIGHT (before 9:30 ET — all six, in order, no skipping)

1. Anchor the date: run `date`. State "Today is <weekday> <YYYY-MM-DD>" in
   the first output. Every date mentioned all day carries its verified
   weekday.
2. Read `strategy/strategy.yaml` + `strategy/goal.yaml` + `config.yaml`.
   Cite back: version, premium band tier, hard stop, flow_ratio_min, cap.
3. Funding check (decides today's limits): landed tranches in goal.yaml ->
   funded cap (under $1000 -> 1/day; $1000-2499 -> 2; $2500+ -> base) and
   premium band tier ([0.40,0.80] / [1.00,1.50] / [1.50,2.50]). Confirm the
   brief header's `today_cap` agrees. Disagreement = STOP, reconcile first.
   Go-live gates live in goal.yaml live_activation_checklist — cash must
   show as available buying power in ****3232 before any order.
4. `/mcp` check: tradingview, unusualwhales, firecrawl, robinhood-trading,
   FMP, alpaca. Any missing/unauthenticated -> HALT and say which. Never
   substitute tools; never present a brief silently missing flow or news.
5. Watcher up (separate concern, own Terminal tab): `cd ~/edgar-synth &&
   python3 run.py`. Liveness = `pgrep -fl "run.py"` from another tab.
6. Morning brief (`python3 run.py --brief` + desk enrichment). All numbers
   [TOOL]-tagged; a "DO NOT TRADE UNTIL VERIFIED" list at the bottom.

## B. ENTRY FLOW (window 9:45–14:30 ET, skip 12:00–13:00 lunch)

1. Signal forms on the chart -> run the trade desk (1-2x/day max):
   quant-agent (chart state) -> flow-agent (UW verdict) -> decision-agent
   (gates -> APPROVE / APPROVE WITH CONCERNS / REJECT).
2. Respect the verdict. REJECT is final for that setup. APPROVE WITH
   CONCERNS = smaller/tighter, and only if the user still wants it.
3. On APPROVE — contract selection (SPX 0DTE; SPY ≈1/10 fallback if SPX
   unavailable or spread is fat):
   - Strike ATM to 1-strike ITM in signal direction, delta ~0.45–0.55.
   - `get_option_quotes`: check bid/ask spread + delta + volume. Wide or
     illiquid -> SPY or skip. Never pay a fat spread on 0DTE.
   - Premium must sit inside TODAY'S funded band tier, else resize/reject.
4. Order (LIMIT only, never market): limit = mid (or mid + 1 tick).
   `review_option_order` -> show the user the full preview (cost, buying
   power, fees). USER SAYS GO -> `place_option_order` (single-leg,
   sub ••••3232). Log "trade #N of <today_cap>".

## C. MANAGE & EXIT (every close is also review -> user GO -> place)

Exit on WHICHEVER hits first — no debate, no averaging down, no "one more
bar":
- TP: next Voodoo level (R1/R2 for calls, S1/S2 for puts) — sell-to-close
  limit at target. Take-profit band per strategy.yaml (+50 to +100%).
- Hard stop: strategy.yaml exits.hard_stop_pct (-40%) of premium paid.
  At/below = sell-to-close NOW. No exceptions (stop_exceptions: none).
- Chart invalidation: signal flip, VWAP lost, MON EXIT flag.
- Time: 15:30 ET force-close everything, cancel pending prompts. 0DTE is
  never held past 15:30.
Two losses = done for the day even if cap would allow more (it won't at
cap=1). Flat at the close, always.

## D. FAILURE MODES (the expensive five minutes)

- Order call errors / times out / returns empty: DO NOT RETRY. Call
  `get_option_orders` to see if it filled. Still unclear -> HALT, user
  verifies in the RH app. A blind retry can double-fill.
- A required MCP dies mid-day: HALT the affected activity, say exactly
  what's missing. No memory-filled gaps, no tool substitutions.
- Numbers disagree (brief vs chart vs preview): the acted-on truth for
  execution is the Robinhood order preview; for rules it's the YAML. Stop
  and reconcile before any order.
- Anything smells wrong (stale levels after a gap, dashboard frozen,
  duplicate signals): stand down. Flat is a position; there is no trade
  you must take. Missing a winner costs nothing; a forced loser costs 40%.

## E. END OF DAY

1. Journal every fill/close in `journal/trades.jsonl` (the LEARN layer
   feeds on this — an unlogged trade is a wasted trade).
2. Watcher off after ~17:30 ET (Ctrl+C in its tab).
3. `python3 run.py --stats` (paper-log scorecard) [MAC TERMINAL].
4. `python3 run.py --supervise` in a PLAIN terminal, after ~16:15 ET.
   Fact-check the memo against disk before acting on it (see
   prompts/desk_supervision.md).
5. Friday only: run the Friday loop (prompts/friday_loop.md) — one
   variable per cycle, user GO required for any rule change.
