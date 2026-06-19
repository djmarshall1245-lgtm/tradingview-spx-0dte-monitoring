# Friday Loop — weekly reflection (the LEARN layer)

Trigger C: run this whenever **either** is true —
  • 5 closed trades have accumulated since the last reflection, OR
  • it's Friday at close.
Whichever comes first. This is the ONLY time strategy.yaml gets edited.

Paste into terminal Claude Code. NO live-data MCP needed — this reads files
only (keeps the run cheap; reflection is about the past, not the present).

---

```
You are running the HERMES weekly reflection loop. Read strategy/goal.yaml,
strategy/strategy.yaml, journal/trades.jsonl, journal/hypotheses.jsonl.
Tag every claim [TOOL]/[STALE]/[MEMORY].

STEP 1 — COMPUTE (use lib/score.py logic):
  From trades closed since the last reflection:
    trade count, win rate, avg win $, avg loss $,
    EXPECTANCY = (win% * avg_win$) - (loss% * avg_loss$),
    total P&L, current equity vs $1000, max drawdown hit.

STEP 2 — CLUSTER BY REGIME (trend_up/trend_down/chop/event_driven):
  Per regime: count, win rate, expectancy. Flag which regimes WORK vs BLEED.
  This is where the edge hides.

STEP 3 — EVALUATE LAST HYPOTHESIS:
  Read the newest hypotheses.jsonl entry with result="pending".
  Compare its success_metric to the actual data. Set result to:
    confirmed / refuted / insufficient_data. Set evaluated_on = today.

STEP 4 — PROPOSE ONE NEW HYPOTHESIS (one-variable rule):
  Change exactly ONE field from strategy.yaml `editable_by_loop`.
  NEVER propose a change to anything in `hard_rails_locked` — if the data
  seems to call for it, STOP and ask me.
  Append a hypotheses.jsonl record: hypothesis_id, week_of, strategy_version,
  one_variable_change, prediction, success_metric, result="pending",
  evaluated_on=null.

STEP 5 — VERSION BUMP (only with my GO):
  If last hypothesis was CONFIRMED and we're keeping the change, write
  strategy.yaml v(N+1) with the one change, and snapshot the prior file to
  strategy/history/v{NNNN}.yaml. Otherwise leave strategy.yaml untouched.
  >>> This edit requires my GO (gate #2 — the rule change). Show me the diff
      first, wait for GO, THEN write.

STEP 6 — HALT TRIGGERS (stop + tell me, no auto-propose):
  expectancy < 0 for 2 straight weeks; equity < $700; any day hit the 10%
  daily DD cap; data implies a hard_rails_locked change.

STEP 7 — REPORT:
  WEEK OF __ | Trades __ | Win __% | Expectancy $__/trade | P&L $__
  Account $__ (was $__, __%)
  Best regime __ ($__ exp) | Worst regime __ ($__ exp)
  Last hypothesis: confirmed/refuted/insufficient
  New hypothesis: __
  Strategy next week: v__ unchanged | v__ bumped (needs your GO)
  Halt triggers: none | __
```
