"""Daily chain snapshot + valuation. [YouTuber #2 / AI Pathways Layer 1-2]

For each watchlist name: pull spot + the option chain via yfinance, save a
dated JSON snapshot (data/snapshots/TICKER_YYYY-MM-DD.json), mirror to SQLite,
compute local Greeks, and value any held positions (mark, P&L, DTE, progress
to target/stop). Required so later runs can diff today vs prior for
new-strike / new-expiry detection and IV history.

Needs yfinance + network. Marks come from the current feed (no historical
chain reconstruction); --asof only stamps the run date for storage/diffing.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import math
from . import db as dbmod
from . import greeks as gk

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "snapshots"


def _mark(bid, ask, last):
    if bid and ask and bid > 0 and ask > 0:
        return round((bid + ask) / 2.0, 4)
    return last


def pull_chain(ticker, asof: str):
    """Returns (spot, rows). rows = list of dicts across all expiries."""
    import yfinance as yf

    tk = yf.Ticker(ticker)
    spot = float(tk.history(period="1d")["Close"].iloc[-1])
    rows = []
    today = datetime.strptime(asof, "%Y-%m-%d").date()
    for expiry in tk.options:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        dte = (exp_date - today).days
        chain = tk.option_chain(expiry)
        for is_call, frame in ((True, chain.calls), (False, chain.puts)):
            for _, r in frame.iterrows():
                mark = _mark(r.get("bid"), r.get("ask"), r.get("lastPrice"))
                rows.append({
                    "ticker": ticker, "strike": float(r["strike"]), "expiry": expiry,
                    "is_call": int(is_call), "bid": float(r.get("bid") or 0),
                    "ask": float(r.get("ask") or 0), "last": float(r.get("lastPrice") or 0),
                    "iv": float(r.get("impliedVolatility") or 0),
                    "volume": 0 if (v := r.get("volume")) is None or (isinstance(v, float) and math.isnan(v)) else int(v),
                    "open_interest": 0 if (oi := r.get("openInterest")) is None or (isinstance(oi, float) and math.isnan(oi)) else int(oi),
                    "mark": mark, "dte": dte, "spot": spot,
                })
    return spot, rows


def save_snapshot(ticker, asof, spot, rows):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{ticker}_{asof}.json"
    path.write_text(json.dumps({"asof": asof, "ticker": ticker, "spot": spot,
                                "rows": rows}, indent=2))
    conn = dbmod.connect()
    with conn:
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO snapshots
                   (asof,ticker,strike,expiry,is_call,bid,ask,last,iv,volume,
                    open_interest,mark) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (asof, ticker, r["strike"], r["expiry"], r["is_call"], r["bid"],
                 r["ask"], r["last"], r["iv"], r["volume"], r["open_interest"], r["mark"]))
            conn.execute(
                """INSERT OR REPLACE INTO iv_history
                   (asof,ticker,strike,expiry,is_call,iv) VALUES (?,?,?,?,?,?)""",
                (asof, ticker, r["strike"], r["expiry"], r["is_call"], r["iv"]))
    conn.close()
    return path


def value_positions(positions, snapshots, asof):
    """positions: list from positions.yaml. snapshots: {ticker: (spot, rows)}."""
    conn = dbmod.connect()
    out = []
    for p in positions:
        key = (p["ticker"], float(p["strike"]), p["expiry"], int(p["side"] == "call"))
        spot, rows = snapshots.get(p["ticker"], (None, []))
        match = next((r for r in rows if (r["ticker"], r["strike"], r["expiry"],
                                          r["is_call"]) == key), None)
        if not match or spot is None:
            out.append({**p, "error": "no live mark"})
            continue
        mark = match["mark"]
        cost = p["premium_paid"]
        g = gk.compute(spot, p["strike"], match["dte"], match["iv"],
                       p["side"] == "call")
        ivr, ivr_label = dbmod.iv_rank(conn, *key, match["iv"])
        tgt, stp = p.get("target_price"), p.get("stop_price")
        prog_t = (mark - cost) / (tgt - cost) * 100 if tgt and tgt != cost else None
        prog_s = (cost - mark) / (cost - stp) * 100 if stp and stp != cost else None
        row = {
            "ticker": p["ticker"], "side": p["side"], "strike": p["strike"],
            "expiry": p["expiry"], "contracts": p["contracts"], "mark": mark,
            "value": round(mark * p["contracts"] * 100, 2),
            "unreal_pnl": round((mark - cost) * p["contracts"] * 100, 2),
            "unreal_pnl_pct": round((mark - cost) / cost * 100, 1) if cost else None,
            "dte": match["dte"], "delta": round(g.delta, 3),
            "theta_day": round(g.theta_per_day * p["contracts"] * 100, 2),
            "vega": round(g.vega_per_1pct * p["contracts"] * 100, 2),
            "iv": round(match["iv"], 4), "iv_rank": ivr, "iv_label": ivr_label,
            "progress_to_target_pct": round(prog_t, 0) if prog_t is not None else None,
            "progress_to_stop_pct": round(prog_s, 0) if prog_s is not None else None,
        }
        out.append(row)
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO valuations
                   (asof,ticker,strike,expiry,is_call,mark,value,unreal_pnl,
                    unreal_pnl_pct,dte,delta,gamma,theta_day,vega,iv,
                    progress_to_target,progress_to_stop)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (asof, p["ticker"], p["strike"], p["expiry"], key[3], mark,
                 row["value"], row["unreal_pnl"], row["unreal_pnl_pct"], match["dte"],
                 g.delta, g.gamma, row["theta_day"], row["vega"], match["iv"],
                 row["progress_to_target_pct"], row["progress_to_stop_pct"]))
    conn.close()
    return out


def run(watchlist, positions, asof=None):
    asof = asof or date.today().isoformat()
    snapshots = {}
    for t in watchlist:
        spot, rows = pull_chain(t, asof)
        save_snapshot(t, asof, spot, rows)
        snapshots[t] = (spot, rows)
    valuations = value_positions(positions, snapshots, asof) if positions else []
    return {"asof": asof, "snapshots": list(snapshots), "valuations": valuations}
