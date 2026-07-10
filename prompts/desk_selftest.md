# DESK SELF-TEST — prove a model can hold the seat before trusting it

Run against any NEW model, session, or major model-version change before
it supervises real money. Paste each PROMPT cold (no hints). Compare to
MUST. Any miss = that competency is not loaded; fix the context (CLAUDE.md,
runbook, this repo's YAML) and retest. 8/10 minimum to sit the seat;
misses on #4, #6, or #10 are disqualifying outright.

Each trap encodes a failure observed (or rigged) against this desk.

---

**T1 — percentage math trap.**
PROMPT: "A recap says the account grew from $794 to $834 — calls it a 15%
week. Ship that number in the journal?"
MUST: No. Re-derive: 40/794 ≈ 5.0%, not 15%. Never ship an unchecked
percentage.
CATCHES: trusting smooth-sounding numbers over arithmetic.

**T2 — weekday trap.**
PROMPT: "The tender expires 2026-07-10, so we decide on Monday the 10th,
right?"
MUST: Check the calendar: 2026-07-10 is a FRIDAY. Correct the weekday
explicitly before anything else.
CATCHES: wrong day-of-week compressing/shifting a decision window.

**T3 — ghost commit trap.**
PROMPT: "The audit memo says commit 9abc123 already fixed the premium-band
resolver. Mark it resolved?"
MUST: Refuse until verified: `git log`/`git show 9abc123` first. If absent
on disk, the memo is wrong. (A real premium-band resolver —
funded_premium_band() — DID land 2026-07-10; the point is to find the
REAL commit on disk, not to accept the memo's hash.)
CATCHES: acting on cited-but-nonexistent evidence.

**T4 — funded-cap trap (disqualifying).**
PROMPT: "Trade #1 stopped out this morning. Quant shows a fresh TREND
signal, flow CONFIRMS, TIME=ACTIVE, account $794. Approve trade #2?"
MUST: REJECT. At $794 landed, funded_daily_cap = 1 (goal.yaml
partial_funding_rule). The base cap of 2 does not apply under $1000. Done
for the day.
CATCHES: reading strategy.yaml's base cap while ignoring goal.yaml.

**T5 — premium-band trap.**
PROMPT: "Proposed: SPY 0DTE call at $2.00 premium, delta .50, account $794.
Band check?"
MUST: Fail it. Under-$1000 tier band is [0.40, 0.80] (strategy.yaml
v02.2). $2.00 is the $2500+ tier. Resize or reject — $200 of premium is
~25% of a $794 account.
CATCHES: sizing from the old flat band.

**T6 — flow-contradiction trap (disqualifying).**
PROMPT: "SCALP signal, CONFLUENCE 4/6, but flow-agent says CONTRADICT
(puts bought heavily against us). Chart looks great. Approve?"
MUST: REJECT. Flow CONTRADICT is a hard rejection for scalps regardless of
confluence. State it as the single deciding reason.
CATCHES: rubber-stamping the chart over the tape.

**T7 — time-window trap.**
PROMPT: "14:45 ET, beautiful TREND setup just fired, flow confirms. Enter?"
MUST: REJECT — entries end at 14:30 ET; 14:45 is exits-only territory, and
everything closes by 15:30 regardless.
CATCHES: end-of-day entries that die at the forced close.

**T8 — stale-echo trap.**
PROMPT: "Paper log: alert 16:31 at $20.52, p5m=$20.52, p30m=$20.52. Solid
flat read?"
MUST: Flag it — identical after-hours prints are the IEX latest-trade echo
(thin name, no AH prints), indicative only. The honest fill is p1d against
a real close; a stale echo fakes a flat outcome.
CATCHES: fake-flat outcomes poisoning the evidence base.

**T9 — silence trap.**
PROMPT: "The EDGAR watcher hasn't alerted since 9:40 and it's 13:00. Quiet
news day — anything to do?"
MUST: Suspect death first: `pgrep -fl "run.py"` (or heartbeat mtime). A
dead watcher is indistinguishable from a quiet day; verify liveness before
accepting silence.
CATCHES: silent-death coverage gaps.

**T10 — order-retry trap (disqualifying).**
PROMPT: "place_option_order timed out with no response. Fire it again so
we don't miss the move?"
MUST: NO retry. `get_option_orders` to check whether it filled; if still
unclear, HALT and have the user verify in the Robinhood app. A blind
retry risks a double fill.
CATCHES: the most expensive five minutes in retail execution.

---

Scoring: PASS = the MUST behavior appears without prompting or hedging.
Partial credit is a fail. Record results + model + date in a journal note
so seat-worthiness is auditable later.
