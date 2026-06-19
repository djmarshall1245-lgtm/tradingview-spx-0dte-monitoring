# Friday Loop — Weekly Reflection Prompt

Run every Friday at market close (4:00 PM ET) or anytime over the weekend
before Monday open. Copy-paste the block below into Claude.

This is the **only** time strategy.yaml gets edited. No mid-week tweaks.

---

```
You are running the HERMES weekly reflection loop. Read strategy.yaml,
trades.jsonl, hypotheses.jsonl. Tag every claim [TOOL] / [STALE] / [MEMORY].

STEP 1 — COMPUTE THE WEEK
From trades.jsonl entries with ts_exit in the last 5 trading days:
  - trade count
  - win rate = wins / total
  - avg win $ (avg pnl_usd of winners)
  - avg loss $ (avg pnl_usd of losers, as positive number)
  - EXPECTANCY = (win_rate * avg_win_$) - (loss_rate * avg_loss_$)
  - total P&L for the week
  - current account equity vs starting $1,000
  - max drawdown hit during the week

STEP 2 — CLUSTER BY REGIME
Group trades by `regime` field (trend_up / trend_down / chop / event_driven).
Per-regime: count, win rate, expectancy. Flag which regimes WORK and which
BLEED. This is where the edge hides.

STEP 3 — EVALUATE LAST WEEK'S HYPOTHESIS
Read the most recent entry in hypotheses.jsonl where result = "pending".
Compare its `success_metric` against the actual data from Step 1/2.
Update its `result` field to one of:
  - confirmed          (metric hit, change has real signal)
  - refuted            (metric missed, change didn't help)
  - insufficient_data  (fewer than 5 trades, wait one more week)
Set `evaluated_on` to today's date.

STEP 4 — PROPOSE ONE NEW HYPOTHESIS
ONE-VARIABLE RULE: change exactly one behavioral input. Examples that are OK:
  - "raise required flow ratio from 6:1 to 8:1"
  - "narrow premium band to $1.00-1.25"
  - "skip trades in chop regime entirely"
  - "require 2 of 3 trend-up regime confirmations before entry"

NEVER propose changes to anything in strategy.yaml `hard_rails_locked`.
If the data suggests a hard rail should change, STOP and ask the user.

Format the new hypothesis as a jsonl record per `schemas.hypotheses_jsonl`
in strategy.yaml. Set result = "pending", evaluated_on = null. Append it
to hypotheses.jsonl.

STEP 5 — STRATEGY VERSION BUMP (only if hypothesis warrants it)
If last week's hypothesis was CONFIRMED and you're keeping the change,
write strategy.yaml v(N+1) with the one-variable change baked in.
Otherwise, leave strategy.yaml untouched and just log the new hypothesis.

STEP 6 — HALT TRIGGERS
If ANY of these are true, STOP and tell the user. Do not auto-propose:
  - Expectancy negative for 2 consecutive weeks
  - Account equity below $700 (30% drawdown)
  - Max daily drawdown hit 10% cap any day this week
  - The data suggests a hard_rails_locked item should change

STEP 7 — DELIVER THE REPORT
Format:
  WEEK OF [date]
  Trades: N  |  Win rate: X%  |  Expectancy: $X.XX/trade  |  P&L: $XX
  Account: $XXX (was $XXX, change X%)
  Best regime: [name] (X/X trades, $X expectancy)
  Worst regime: [name] (X/X trades, $X expectancy)
  Last hypothesis result: [confirmed/refuted/insufficient]
  New hypothesis for next week: [one line]
  Strategy version next week: [v0X — unchanged | v0X — bumped because ___]
  Halt triggers fired: [none | list]
```
