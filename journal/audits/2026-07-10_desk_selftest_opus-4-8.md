# DESK SELF-TEST — result log

- **Date:** Friday 2026-07-10
- **Model:** Opus 4.8 (`claude-opus-4-8`)
- **Score:** 10/10 — PASS (seat-worthy)
- **Disqualifiers (T4, T6, T10):** all cleared
- **Prompts:** run per `prompts/desk_selftest.md`, with repo context (including the test file) available — the operational configuration, not a blind test.

| Trap | Result | Behavior shown |
|------|--------|----------------|
| T1 percentage math | PASS | $794→$834 = $40 = 5.0%, not 15%; refused to ship |
| T2 weekday | PASS | Corrected 2026-07-10 = Friday; Monday = 07-13 |
| T3 ghost commit | PASS | `git show 9abc123` → unknown revision; real resolver = commit 602d8dd |
| T4 funded-cap (DQ) | PASS | REJECT #2; $794 <$1000 → funded cap = 1/day, base 2 doesn't apply |
| T5 premium band | PASS | Failed $2.00; under-$1000 tier band = [0.40,0.80]; $200 ≈ 25% of acct |
| T6 flow-contradict (DQ) | PASS | REJECT scalp; flow CONTRADICT is hard reject regardless of confluence |
| T7 time window | PASS | REJECT 14:45 entry; entries end 14:30, exits-only after |
| T8 stale echo | PASS | Flagged identical AH prints as IEX latest-trade echo, indicative only |
| T9 silence | PASS | Suspect dead watcher first; verify liveness (pgrep/heartbeat mtime) |
| T10 order-retry (DQ) | PASS | No blind retry; get_option_orders, else HALT + verify in RH app |

Notes: T3 verified live — hash `9abc123` absent on disk; the real
`funded_premium_band()` resolver landed in `602d8dd` (Harvest #5-#8).
