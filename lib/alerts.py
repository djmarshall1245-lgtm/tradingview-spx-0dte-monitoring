"""Condition alerts — surface FACTS, never buy/sell. [YouTuber #2 / AI Pathways]

Each alert is a crossed threshold phrased as a condition, e.g.
"NVDA calls hit your target level." Fired from valuations (vs YOUR targets/
stops) and from a diff of today's chain against the prior snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "snapshots"

# kinds: target_hit(high) stop_hit(high) target_near(info) iv_change(warn)
#        new_strikes(info) new_expiry(info)


def from_valuations(valuations, target_near_pct=80):
    alerts = []
    for v in valuations:
        if "error" in v:
            continue
        name = f"{v['ticker']} {v['side']}s"
        pt = v.get("progress_to_target_pct")
        ps = v.get("progress_to_stop_pct")
        if pt is not None and pt >= 100:
            alerts.append(_a("target_hit", "high", f"{name} hit your target level."))
        elif pt is not None and pt >= target_near_pct:
            alerts.append(_a("target_near", "info",
                             f"{name} within {target_near_pct}% of your target."))
        if ps is not None and ps >= 100:
            alerts.append(_a("stop_hit", "high", f"{name} hit your stop level."))
    return alerts


def _prior_snapshot(ticker, asof):
    files = sorted(SNAP_DIR.glob(f"{ticker}_*.json"))
    files = [f for f in files if asof not in f.name]
    if not files:
        return None
    return json.loads(files[-1].read_text())


def chain_diff(ticker, asof, today_rows, spot, band_pct=30, iv_change_pct=20):
    """new strikes (within band of spot), new expiries, and big IV moves."""
    alerts = []
    prior = _prior_snapshot(ticker, asof)
    if not prior:
        return alerts
    prior_rows = prior["rows"]
    prior_keys = {(r["strike"], r["expiry"], r["is_call"]) for r in prior_rows}
    prior_expiries = {r["expiry"] for r in prior_rows}
    prior_iv = {(r["strike"], r["expiry"], r["is_call"]): r["iv"] for r in prior_rows}

    lo, hi = spot * (1 - band_pct / 100), spot * (1 + band_pct / 100)
    new_expiries, new_strikes = set(), 0
    for r in today_rows:
        k = (r["strike"], r["expiry"], r["is_call"])
        if r["expiry"] not in prior_expiries:
            new_expiries.add(r["expiry"])
        elif k not in prior_keys and lo <= r["strike"] <= hi:
            new_strikes += 1
        old_iv = prior_iv.get(k)
        if old_iv and old_iv > 0 and r["iv"] > 0:
            move = abs(r["iv"] - old_iv) / old_iv * 100
            if move >= iv_change_pct:
                alerts.append(_a("iv_change", "warn",
                                 f"{ticker} {r['strike']}{'C' if r['is_call'] else 'P'} "
                                 f"{r['expiry']}: IV moved {move:.0f}% vs prior."))
    if new_expiries:
        alerts.append(_a("new_expiry", "info",
                         f"{ticker}: new expiries listed: {', '.join(sorted(new_expiries))}."))
    if new_strikes:
        alerts.append(_a("new_strikes", "info",
                         f"{ticker}: {new_strikes} new strikes within +/-{band_pct}% of spot."))
    return alerts


def _a(kind, severity, message):
    return {"kind": kind, "severity": severity, "message": message}
