# Monday Desk Loop — 2026-07-06 (SPY 0DTE via robinhood_bot.py)

Trigger phrase (say this Monday at the desk): **"Start the Monday desk loop."**
Claude then runs `/loop 5m` with the cycle below. The loop is started MANUALLY
by Andre — never scheduled/unattended (LaunchAgents post-mortem applies).

## Hard rules (non-negotiable)
- **MANUAL APPROVAL ON EVERY ORDER.** Loop may run `review_option_order` and
  show the preview, then it STOPS and waits for Andre's explicit "GO".
  `place_option_order` only after GO. Never auto-fire. Every exit too.
- Account: agentic sandbox ••••3232 only. Single-leg. Limit at mid only.
- Daily cap: 2 trades. Two losses = done. No entries 12:00–1:00 or after 2:30 ET.
- Loop window: 9:45 AM – 2:30 PM ET Mon 2026-07-06. Stop the loop at 2:30.
- No blind retries on order errors — check get_option_orders, then halt + ask.

## Preconditions (run once before starting the loop)
1. Read `strategy/strategy.yaml` + `strategy/goal.yaml` (source of truth).
2. `/mcp` — all servers connected (tradingview, unusualwhales, robinhood-trading,
   FMP, alpaca, firecrawl).
3. FMP marketHours — confirm NYSE open (Mon 2026-07-06 is a normal session).
4. `date` — anchor today + weekday.

## Each 5-minute cycle
1. Pull live inputs (all [TOOL], re-pulled fresh every cycle):
   - `spot`: alpaca stockLatestTradeSingle SPY
   - `vwap`, `ema_5`, `ema_13`, `ema_21`: compute from alpaca 1-min SPY bars
     (chart only has EMA 8/21 — bot needs 5/13/21, so compute, don't read chart)
   - `net_gex`: UW get_greek_exposure_by_ticker SPY (call_gamma + put_gamma,
     latest date; use 1W timeframe — 1D returns empty)
   - `vold`, `add`: TradingView data_get_study_values → Market Internals Suite
     (TICK & ADD)
2. `get_option_chains` SPY → today's 0DTE expiration (chain is holiday-aware).
   ATM strike = round(spot). `get_option_quotes` → bid/ask (+ delta, volume).
3. Write `payload.json`, run:
   `python3 robinhood_bot.py --data payload.json`
4. Append cycle output to `monday_execution.log` with timestamp.
5. If NEUTRAL or spread-guard skip → log, sleep, next cycle.
6. If BUY_CALL / BUY_PUT ticket emitted:
   a. `review_option_order` with the ticket (limit at mid).
   b. STOP. Show Andre the preview (cost, bid/ask, delta, trade #_ of 2).
   c. Wait for explicit GO. No GO = no order. Then resume loop.
7. If a position is open: manage per strategy.yaml — hard stop
   `exits.hard_stop_pct` (currently -40%), TP next Voodoo, 3:30 close-out.
   Every close also = review → GO → place.

## Logging format (monday_execution.log)
[HH:MM ET] cycle N | signal | spot | key gate values | action taken
