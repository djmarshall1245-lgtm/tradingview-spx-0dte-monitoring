# Quant-trading deep research — findings & Friday-loop candidates

Written Sun 2026-07-12 (cloud session). Source: multi-agent deep-research
workflow `wf_0ffe4880-3af` — 5 search angles, 19 sources (9 primary),
62 claims extracted, 25 sent to adversarial verification (3 independent
refute-votes each). Stopped on user request before the final verify pass;
resumable later via `resumeFromRunId: wf_0ffe4880-3af` (cached — only the
17 pending votes + synthesis would re-run).

STATUS LEGEND (applies to every claim below):
- ✅ CONFIRMED 3-0 — survived three independent adversarial refute-votes.
- ⏳ PRIMARY-SOURCED, UNVERIFIED — quote pulled from the primary paper
  but the refute-votes were killed by the session usage limit. Treat as
  [STALE]-class: strong, but re-verify before it justifies a RULE change.

---

## 1. What the research VALIDATES that the desk already encodes

No action needed — these are citations for rails already in
`strategy/strategy.yaml` / `strategy/goal.yaml`. Do not add duplicate rules.

| Documented finding | Status | Existing rail |
|---|---|---|
| Retail 0DTE losses concentrate in single-leg, upfront-premium, HIGH-IV trades (SSRN 4404704) | ⏳ | `gates.iv_filter` — stand down at IV rank ≥70; 30–70 conditional on TREND+flow |
| Avg long retail 0DTE position lost 53% (61% since May-2022) of value (SSRN 4404704) | ⏳ | `exits.hard_stop_pct: -40`, funded cap 1/day, 2-losses-done |
| Retail avg loss/trade ≈ −0.9% vs 5–10% quoted spreads → limit orders are the survival mechanism (LSU retail_option_trading_v2) | ⏳ | `execution.order_type: limit_only`, limit at mid |
| Published edges decay ~26% out-of-sample, ~58% post-publication (McLean & Pontiff, hec.ca/finance/Fichier/McLean.pdf) | ✅ 3-0 | `objective.primary_metric: expectancy_per_trade` rolling-20 — the AR Squeeze edge is MEASURED, not trusted |
| Time-series momentum persists 1–12 months then reverses — a multi-week edge, not intraday (Moskowitz-Ooi-Pedersen, ssrn 2089463) | ✅ 3-0 | Confirms: no drift toward "intraday trend-following" lore; the desk's edge claim is flow+levels, not TSM |
| TSM "significant in ALL 58 instruments" is overstated (replications show ~52/58) | ❌ REFUTED 0-3 | Reminder that even canonical papers get quoted beyond their evidence |
| Hedge-fund track records inflated by backfill + survivorship bias (CFA Institute FAJ 2009) | ⏳ | Reinforces sourcing rules: [TOOL]/[MEMORY] tags, primary sources only |

## 2. Candidate A — RECOMMENDED for Friday loop 2026-07-17 (one variable)

**Numeric spread gate + cost-drag journaling.**

Evidence (all ⏳ primary-sourced — re-verify before GO):
- ~60% of retail daily 0DTE losses are attributable to TRANSACTION COSTS;
  even meaningful price improvement doesn't flip retail 0DTE profitable
  on average. (SSRN 4404704, "Retail Traders Love 0DTE Options")
- Retail pays an average bid-ask spread of **12.6% of option price** on
  short-dated contracts (Journal of Finance, doi 10.1111/jofi.13285);
  aggregate retail options losses were dominated by indirect trading
  costs ($6.4bn costs vs $2.1bn net loss, Nov-2019→Jun-2021).
- ~90% of retail PFOF goes to three wholesalers — the spread is the
  counterparty's verified edge. (same JoFi paper)

Gap in the current YAML: `instrument.liquidity_screen.max_spread: tight`
is a WORD, not a number — unfalsifiable at the gate. And
`journal/trades.jsonl` records fills but not fill-vs-mid, so the
expectancy metric can't decompose losses into "edge failed" vs "spread
ate it" — exactly the distinction the research says decides retail
survival.

Proposed change (needs Friday-loop GO, one variable):
1. `liquidity_screen.max_spread` → numeric: **(ask−bid)/mid ≤ 5%**, else
   SPY-or-skip. Sanity: a $0.60 SPY 0DTE ATM at $0.01–0.02 wide = 1.7–3.3%,
   so 5% passes normal fills and blocks only genuinely bad ones.
2. Journal schema addition — at every fill (entry AND exit) log:
   `bid`, `ask`, `mid`, `fill`, derived `cost_drag_pct`
   (= |fill−mid|/mid, signed round-trip total per trade).
   After ~20 trades the rolling expectancy splits into gross-edge vs
   cost-drag. If cost-drag ≥ the documented ~60% share of losses, the
   fix is execution (patience at mid, SPY over SPX), not signal quality.

Costs nothing, loosens nothing, touches no hard rail.

## 3. Candidate B — PARKED until $2500+ tier

**Defined-risk premium selling (spreads), not more premium buying.**
- Variance risk premia strongly negative for S&P/Dow — sellers of index
  variance earn a documented premium; buyers structurally pay it
  (Carr & Wu, RFS 2009 — ✅ 3-0). Short/premium-selling 0DTE positions
  were profitable on average even after fees while long lost 53–61%
  (SSRN 4404704 — ⏳).
- The desk is a long-premium buyer BY DESIGN (defined risk = premium
  paid; correct at this account size).
- Blocked today anyway: Robinhood MCP is single-leg only (no spreads),
  and naked selling is out of the question. Revisit at the $2500+ or
  $5000 tier in `scale_up_plan` — defined-risk structures (verticals)
  only, and only if broker capability exists then.

## 4. Note C — doctrine citation, zero config change

**0DTE gamma does NOT create squeezes.** Higher 0DTE open-interest gamma
is associated with REDUCED intraday volatility, not squeezes (SSRN
4692190 — ⏳). "Gamma squeeze incoming" headlines are never a
conviction-raiser; the flow-agent's GEX regime read from UW numbers is
the only gamma input. This is DATA BEATS NARRATIVE with a citation.

## 5. Primary sources

- SSRN 4404704 — Retail Traders Love 0DTE Options (retail 0DTE P&L, cost share)
- Journal of Finance 10.1111/jofi.13285 — retail options costs, 12.6% spreads, PFOF concentration
- LSU retail_option_trading_v2.pdf — trade-level retail options outcomes, 0DTE −4.7pp underperformance (⏳)
- Carr & Wu, RFS 2009 (engineering.nyu.edu PDF) — variance risk premium ✅
- Moskowitz, Ooi & Pedersen, JFE 2012 (ssrn 2089463) — time-series momentum ✅
- McLean & Pontiff (hec.ca PDF) — post-publication edge decay ✅
- SSRN 4692190 — 0DTE gamma and intraday volatility (⏳)
- CFA Institute FAJ 2009 — hedge-fund database biases (⏳)

Full claim set with verbatim quotes: workflow output (cloud session
`wv1gdlsnx.output`); resume the verify pass with
`resumeFromRunId: wf_0ffe4880-3af` if the ⏳ claims need confirmation
before Friday.

## 6. Candidate D — queued 2026-07-15: package the trade desk as a skill

Owner decision Wed 2026-07-15: NOT this week (one-variable discipline,
go-live week). Move (not copy) the Live Trade Desk procedure from
CLAUDE.md into `.claude/skills/spx-0dte-desk/SKILL.md`; CLAUDE.md section
shrinks to a 3-line pointer. Skill step 0 = read strategy.yaml +
goal.yaml (numbers stay in YAML — procedure only, no values). Win:
~2-3k tokens off every session + one canonical trigger. Zero decision-
quality change. Build only with Friday-loop GO.

## 7. Candidate E — queued 2026-07-15: AR Squeeze v3 chart-layer toggles

Fable 5 audit of the live Pine Script (v2) found 3 defects + 4 upgrades.
v3 is written and pushed: `scratch/ar_squeeze_pro_max_v3_2026-07-15.pine`.

REPAIRS baked in (defect fixes, not rule changes — swap ASAP, no GO gate):
- R1 broken alert placeholders ({{low[1]}} printed literally — no stop
  price in any alert since day 1)
- R2 $TICK exit knife-edge (exit fired at the entry threshold → chopped
  out of working trades within minutes; now hysteresis: enter ±200,
  exit through 0)
- R3 MTF squeeze repaint (15m/30m used the live developing bar; now
  confirmed-bar idiom + signals-on-bar-close gate)

TOGGLES default OFF (= v2 behavior) — each is ONE Friday-loop variable:
- T4 nearest-Voodoo TP (never target a level already passed)
- T5 desk entry window 09:45–14:30 + lunch skip (mirrors strategy.yaml —
  arguably a repair since the rule already exists; still gated for
  discipline)
- T6 TLT filter mode: 1-bar (v2, noise) / 30-bar slow / OFF
- T7 auto PDH/PDL from prior daily bar (kills stale-level failure mode)

After swapping scripts on TradingView: recreate all 6 alerts, trigger
"Once Per Bar Close". Alert names unchanged. quant-agent reads the same
dashboard/labels — no agent changes needed (script title changed to
"AR SQUEEZE PRO MAX v3 + LABELS"; if data_get_pine_labels filters on
study title "AR SQUEEZE", the substring still matches).
