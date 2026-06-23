"""Overnight tells — the pre-open global tape. [User-requested context layer]

Pulls the cross-asset signals US traders watch before 9:30 ET, via yfinance
(same free source as the rest of the OBSERVE layer). Deterministic: same data
in, same read out. Reports each tell's overnight % change + a risk-on/off
synthesis. NOT a trade trigger — context for the macro regime.

Ticker list is config-driven (config.yaml -> overnight_tells), so you can
prune or expand without touching code.
"""
from __future__ import annotations

from dataclasses import dataclass

# Default core set (overridable in config.yaml). label -> yfinance symbol.
DEFAULT_TELLS = {
    # US futures — the direct read
    "/ES (S&P fut)":   "ES=F",
    "/NQ (Nasdaq fut)": "NQ=F",
    # Volatility
    "VIX":             "^VIX",
    # Macro pressure
    "10Y yield":       "^TNX",
    "Dollar (DXY)":    "DX-Y.NYB",
    "USD/JPY":         "JPY=X",
    # Cross-asset
    "Crude (WTI)":     "CL=F",
    "Copper":          "HG=F",
    "Gold":            "GC=F",
    "Bitcoin":         "BTC-USD",
    # Asia chip tell
    "Nikkei":          "^N225",
    "KOSPI":           "^KS11",
    # Europe
    "DAX":             "^GDAXI",
}

# Which tells, when UP, mean risk-ON (for the synthesis line).
_RISK_ON_WHEN_UP = {"/ES (S&P fut)", "/NQ (Nasdaq fut)", "Copper", "Bitcoin",
                    "Nikkei", "KOSPI", "DAX"}
# Which tells, when UP, mean risk-OFF.
_RISK_OFF_WHEN_UP = {"VIX", "Gold", "Dollar (DXY)"}
# 10Y up and USD/JPY up are nuanced (rates up = tech pressure; JPY up vs USD
# i.e. JPY=X DOWN = yen strength = risk-off). Handled in the note, not the tally.


@dataclass
class Tell:
    label: str
    symbol: str
    last: float | None
    pct: float | None     # overnight/last-session % change
    err: str | None = None


def _pct_change(symbol):
    import yfinance as yf
    t = yf.Ticker(symbol)
    # 5d window (not 2d): foreign indices (Nikkei/KOSPI/DAX) and rate symbols
    # (^TNX) can have holiday/timezone gaps that leave a 2d window with <2 rows.
    hist = t.history(period="5d")
    if hist is not None and not hist.empty:
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
            return last, (last / prev - 1) * 100 if prev else None
        if len(closes) == 1:
            return float(closes.iloc[-1]), None
    # fall back to fast_info if history is empty/thin
    fi = getattr(t, "fast_info", {}) or {}
    last = fi.get("last_price")
    prev = fi.get("previous_close")
    if last and prev:
        return float(last), (float(last) / float(prev) - 1) * 100
    return (float(last) if last else None), None


def pull(tells: dict | None = None) -> list[Tell]:
    tells = tells or DEFAULT_TELLS
    out = []
    for label, symbol in tells.items():
        try:
            last, pct = _pct_change(symbol)
            out.append(Tell(label, symbol, last, pct))
        except Exception as e:  # one bad ticker never kills the brief
            out.append(Tell(label, symbol, None, None, err=str(e)[:60]))
    return out


def synthesize(tells: list[Tell]) -> str:
    """One-line risk-on/off read from the tally of directional tells."""
    score = 0
    for t in tells:
        if t.pct is None:
            continue
        if t.label in _RISK_ON_WHEN_UP:
            score += 1 if t.pct > 0 else -1
        elif t.label in _RISK_OFF_WHEN_UP:
            score += -1 if t.pct > 0 else 1
    if score >= 3:
        return f"RISK-ON lean (tally +{score})"
    if score <= -3:
        return f"RISK-OFF lean (tally {score})"
    return f"MIXED / no clear lean (tally {score:+d})"


def report(tells: dict | None = None) -> str:
    rows = pull(tells)
    lines = ["⓪ OVERNIGHT TELLS  [TOOL] yfinance (pre-open global tape)"]
    for t in rows:
        if t.err or t.pct is None:
            lines.append(f"   {t.label:<18} n/a  ({t.err or 'no data'})")
        else:
            arrow = "▲" if t.pct > 0 else "▼" if t.pct < 0 else "•"
            val = f"{t.last:,.2f}" if t.last is not None else "—"
            lines.append(f"   {t.label:<18} {arrow} {t.pct:+.2f}%   ({val})")
    lines.append(f"   → {synthesize(rows)}")
    lines.append("   (context for the macro regime — NOT a trade trigger)")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
