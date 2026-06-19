"""Black-Scholes Greeks, computed locally — no external lib.

[YouTuber #2 / AI Pathways pattern] An independent valuation layer so you
never depend on a broker's displayed Greeks, and have a fallback if a data
source is down. Pure standard library (math + statistics.NormalDist).

Inputs use actual days-to-expiry and a configurable annual risk-free rate
(default 0.045). All functions are pure: same inputs -> same outputs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()  # standard normal
DEFAULT_RISK_FREE = 0.045


def _d1_d2(spot, strike, t_years, iv, r):
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None, None
    vol_sqrt_t = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta_per_day: float   # dollars of extrinsic decay per calendar day, per share
    vega_per_1pct: float   # dollars per 1 IV point (1%), per share
    price: float           # BS theoretical price per share


def compute(spot, strike, days_to_expiry, iv, is_call, r=DEFAULT_RISK_FREE) -> Greeks:
    """Greeks for one option. iv as a decimal (0.45 == 45%). days actual calendar days."""
    t = max(days_to_expiry, 0) / 365.0
    d1, d2 = _d1_d2(spot, strike, t, iv, r)
    if d1 is None:
        # Expired / degenerate: intrinsic only, no time value, no sensitivities.
        intrinsic = max(spot - strike, 0.0) if is_call else max(strike - spot, 0.0)
        return Greeks(delta=(1.0 if (is_call and spot > strike) else
                             -1.0 if (not is_call and spot < strike) else 0.0),
                      gamma=0.0, theta_per_day=0.0, vega_per_1pct=0.0, price=intrinsic)

    pdf_d1 = _N.pdf(d1)
    disc = math.exp(-r * t)

    if is_call:
        delta = _N.cdf(d1)
        price = spot * _N.cdf(d1) - strike * disc * _N.cdf(d2)
        theta_annual = (-(spot * pdf_d1 * iv) / (2 * math.sqrt(t))
                        - r * strike * disc * _N.cdf(d2))
    else:
        delta = _N.cdf(d1) - 1.0
        price = strike * disc * _N.cdf(-d2) - spot * _N.cdf(-d1)
        theta_annual = (-(spot * pdf_d1 * iv) / (2 * math.sqrt(t))
                        + r * strike * disc * _N.cdf(-d2))

    gamma = pdf_d1 / (spot * iv * math.sqrt(t))
    vega = spot * pdf_d1 * math.sqrt(t)        # per 1.00 (100%) change in IV
    return Greeks(
        delta=delta,
        gamma=gamma,
        theta_per_day=theta_annual / 365.0,
        vega_per_1pct=vega / 100.0,            # scale to 1 IV point
        price=price,
    )


def implied_from_chain_row(row, spot, is_call, r=DEFAULT_RISK_FREE) -> Greeks:
    """Convenience: row is a dict with strike, days_to_expiry, impliedVolatility."""
    return compute(
        spot=spot,
        strike=float(row["strike"]),
        days_to_expiry=float(row["days_to_expiry"]),
        iv=float(row["impliedVolatility"]),
        is_call=is_call,
        r=r,
    )


if __name__ == "__main__":
    # quick self-check: ATM call, 30 DTE, 30% IV
    g = compute(spot=100, strike=100, days_to_expiry=30, iv=0.30, is_call=True)
    print(f"ATM call  delta={g.delta:.3f}  gamma={g.gamma:.4f}  "
          f"theta/day={g.theta_per_day:.4f}  vega/1%={g.vega_per_1pct:.4f}  "
          f"price={g.price:.3f}")
