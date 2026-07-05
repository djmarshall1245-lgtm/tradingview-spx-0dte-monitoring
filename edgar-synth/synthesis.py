"""Phase 3: the compound signal. Filing conviction x short structure x flow skew.

Score 0-100. The individual feeds are commoditized; this join is the edge.

  conviction_factor : LLM materiality 0-10 -> 0-1
  short_factor      : borrow fee + (bear-only) availability squeeze context.
                      Amplifies BULL signals on hard-to-borrow names (squeeze fuel)
                      and BEAR signals when shorts are already crowded gets *damped*
                      (late to the trade).
  flow_factor       : premium-weighted call/put skew ALIGNMENT with the filing
                      direction. Flow agreeing with the filing before/as it drops
                      is the "someone knew" tell.
"""


def _short_factor(direction, short):
    fee = short.get("fee_rate", 0.0)            # e.g. 0.35 = 35% borrow
    fee_score = min(fee / 0.5, 1.0)             # saturate at 50% fee
    if direction == "bull":
        return fee_score                        # high fee + bull filing = squeeze fuel
    if direction == "bear":
        return max(0.0, 0.6 - fee_score)        # crowded short dampens fresh bear signal
    return 0.0


def _flow_factor(direction, flow):
    skew = flow.get("skew", 0.0)                # -1 (all puts) .. +1 (all calls)
    if flow.get("alert_count", 0) == 0:
        return 0.0
    if direction == "bull":
        return max(0.0, skew)
    if direction == "bear":
        return max(0.0, -skew)
    return 0.0


def score(cfg, verdict, short, flow):
    """cfg = config['synthesis']. Returns (score_0_100, breakdown_dict)."""
    direction = verdict.get("direction", "neutral")
    conviction = verdict.get("conviction", 0) / 10.0
    sf = _short_factor(direction, short or {})
    ff = _flow_factor(direction, flow or {})
    if direction == "neutral":
        return 0.0, {"conviction": conviction, "short": sf, "flow": ff}
    total = (cfg["w_conviction"] * conviction +
             cfg["w_short"] * sf +
             cfg["w_flow"] * ff) * 100.0
    return round(total, 1), {"conviction": conviction, "short": round(sf, 3), "flow": round(ff, 3)}
