# edgar-synth score calibration — week-1 observations (2026-07-06 → 07-10)

INPUT for a FUTURE Friday loop. Nothing here is a change; paper-only data
collection continues as-is. When a calibration change is proposed, it goes
through the Friday loop with user GO, one variable per cycle, like every
other rule.

## How the score composes (synthesis.py + config.yaml)

score = (0.5 * conviction/10 + 0.3 * short_factor + 0.2 * flow_factor) * 100
alert requires score >= 60 AND conviction >= 7.

## Observation 1 — bear verdicts are structurally capped below bulls

- `_short_factor` for bulls returns fee_score (0..1, squeeze fuel); for
  bears it returns max(0, 0.6 - fee_score) — capped at 0.6 by design
  (crowded short = late). Max possible bear score is 88 vs 100 for bulls.
- Observed live: conv=9 bear filings RXT and ZSQR scored 45.0, conv=6 XMAX
  scored 30.0 — i.e. BOTH non-conviction legs were zero, so score =
  conviction leg alone (0.5 * conv/10 * 100). A conviction-9 bear cannot
  alert (45 < 60) unless the flow leg fires, which it rarely does (obs 2).
- Consequence: the alert stream is effectively LONG-BIASED. High-conviction
  bear filings die silently at ~45. Whether that's a bug or a feature is a
  Friday-loop question — the p1d fills on those non-alerted bears (in the
  paper DB) are the evidence to decide with.

## Observation 2 — the flow leg is almost always zero on this universe

- `_flow_factor` returns 0.0 when alert_count == 0. On a $100M–$2B
  small-cap universe, UW-style flow alerts are rare; near-zero flow
  participation is the norm, so the 0.2 weight is dead weight most days.
- First non-zero flow factor observed: EFOR 0.87 on 07-09 — which produced
  the week's closest near-miss at 59.8 (0.2 points under threshold).
- Consequence: in practice alerts need conviction >= 7 AND a meaningful
  short_factor (hard-to-borrow bull, e.g. RXST 70 = conv 9 + fee leg).
  The effective gate is tighter than the config suggests.

## Week-1 outcomes to score against (paper DB has the fills)

- Alerted: RXST 70/conv9 (real catalyst — Alcon deal), RMIX 65, OPRT 61,
  PRME, EOLS. p1d fills logged.
- Near-miss: EFOR 59.8 (flow leg fired, still under).
- Silent bears: RXT 45/conv9, ZSQR 45/conv9, XMAX 30/conv6.

## Candidate one-variable changes (pick AT MOST ONE, future loop, user GO)

1. Separate bear alert threshold (e.g. bear_score_min ~45–50) — accepts
   the structural cap instead of fighting it.
2. Rescale bear short_factor (0.6 cap → 1.0 with different shape) — only
   if week-2+ paper data shows silent bears actually moved.
3. Redistribute the dead flow weight (0.5/0.3/0.2 → e.g. 0.6/0.3/0.1) —
   only with evidence flow alignment isn't predictive here.

Decide from p1d/p30m outcomes in the paper DB, not from theory. More weeks
of data first; the DB is the ground truth.
