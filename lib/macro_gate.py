"""Macro Gate — a deterministic 0-100 market score. [YouTuber #2 / AI Pathways]

Same data in, same score out. Blends VIX level (1yr percentile), VIX term
structure (VIX vs VIX3M), breadth (SPY vs its 200d MA proxy), and credit
(HYG vs TLT). Higher score = calmer / more risk-on environment.

NOT a trade trigger. It tags the regime the book sits in. Needs yfinance
(free). Run on a machine with network; the remote container has none.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class MacroScore:
    score: float
    vix: float
    vix_pctile: float
    term_structure: float
    breadth: float
    credit: float
    regime: str

    def as_dict(self):
        return asdict(self)


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _pct_rank(series, value):
    vals = [v for v in series if v == v]  # drop NaN
    if not vals:
        return 50.0
    below = sum(1 for v in vals if v <= value)
    return 100.0 * below / len(vals)


def compute(weights=None, risk_free=0.045) -> MacroScore:
    import yfinance as yf

    w = weights or {"vix_level": 0.30, "term_structure": 0.25,
                    "breadth": 0.25, "credit": 0.20}

    def hist(t, period="1y"):
        return yf.Ticker(t).history(period=period)["Close"].dropna()

    vix = hist("^VIX")
    vix3m = hist("^VIX3M")
    spy = hist("SPY")
    hyg = hist("HYG")
    tlt = hist("TLT")

    vix_now = float(vix.iloc[-1])
    vix3m_now = float(vix3m.iloc[-1])

    # 1) VIX level: low percentile (calm) -> high score
    vix_pctile = _pct_rank(list(vix), vix_now)
    s_vix = 100.0 - vix_pctile

    # 2) Term structure: contango (VIX < VIX3M) = calm -> high score
    spread_pct = (vix3m_now - vix_now) / vix3m_now * 100.0 if vix3m_now else 0.0
    s_term = _clamp(50.0 + spread_pct * 5.0)

    # 3) Breadth proxy: SPY vs its 200d MA
    ma200 = float(spy.tail(200).mean())
    spy_now = float(spy.iloc[-1])
    s_breadth = _clamp(50.0 + (spy_now / ma200 - 1.0) * 500.0)

    # 4) Credit: HYG/TLT vs its 50d MA (rising risk appetite -> high score)
    ratio = (hyg / tlt).dropna()
    ratio_now = float(ratio.iloc[-1])
    ratio_ma = float(ratio.tail(50).mean())
    s_credit = _clamp(50.0 + (ratio_now / ratio_ma - 1.0) * 1000.0)

    score = (w["vix_level"] * s_vix + w["term_structure"] * s_term
             + w["breadth"] * s_breadth + w["credit"] * s_credit)

    if score >= 65 and spy_now >= ma200:
        regime = "trend_up"
    elif score <= 35 or spy_now < ma200 * 0.97:
        regime = "trend_down"
    else:
        regime = "chop"

    return MacroScore(
        score=round(score, 1), vix=round(vix_now, 2), vix_pctile=round(vix_pctile, 1),
        term_structure=round(s_term, 1), breadth=round(s_breadth, 1),
        credit=round(s_credit, 1), regime=regime,
    )


if __name__ == "__main__":
    try:
        m = compute()
        print(f"MACRO {m.score}/100  regime={m.regime}  "
              f"(VIX {m.vix}, pctile {m.vix_pctile}, term {m.term_structure}, "
              f"breadth {m.breadth}, credit {m.credit})")
    except Exception as e:
        print(f"macro_gate needs yfinance + network: {e}")
