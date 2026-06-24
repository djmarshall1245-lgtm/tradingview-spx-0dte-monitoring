"""Tastytrade market-data client — DATA ONLY, no execution. [User-added]

Tastytrade's API is built for options. The headline value here is the
/market-metrics endpoint: it returns IV RANK, IV percentile, implied vol,
beta, and liquidity per symbol INSTANTLY — no 20-day snapshot ramp needed.
That's a professional-grade IV-rank signal for the watchlist, today.

Auth: OAuth2 refresh flow. Reads three secrets from the environment
(never hardcoded, never committed — see .env.example):
    TASTYTRADE_CLIENT_ID
    TASTYTRADE_CLIENT_SECRET
    TASTYTRADE_REFRESH_TOKEN
Put them in a local .env (gitignored). This module loads them at call time
and fails LOUD with a clear message if any is missing.

Execution is intentionally NOT implemented. This pulls data; orders stay
on Robinhood ****3232.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://api.tastytrade.com"
_TOKEN_CACHE = {"access": None}   # cache access token for the process lifetime


def _load_env_file():
    """Best-effort: load KEY=VALUE lines from a local .env if present."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _creds():
    _load_env_file()
    cid = os.environ.get("TASTYTRADE_CLIENT_ID")
    secret = os.environ.get("TASTYTRADE_CLIENT_SECRET")
    refresh = os.environ.get("TASTYTRADE_REFRESH_TOKEN")
    missing = [n for n, v in [("TASTYTRADE_CLIENT_ID", cid),
                              ("TASTYTRADE_CLIENT_SECRET", secret),
                              ("TASTYTRADE_REFRESH_TOKEN", refresh)] if not v]
    if missing:
        raise RuntimeError(
            "Tastytrade creds missing: " + ", ".join(missing) +
            ". Put them in a local .env (gitignored) — see .env.example.")
    return cid, secret, refresh


def _access_token(force=False):
    if _TOKEN_CACHE["access"] and not force:
        return _TOKEN_CACHE["access"]
    cid, secret, refresh = _creds()
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": cid,
        "client_secret": secret,
    }).encode()
    req = urllib.request.Request(f"{BASE}/oauth/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        tok = json.loads(resp.read()).get("access_token")
    if not tok:
        raise RuntimeError("Tastytrade OAuth returned no access_token — check creds.")
    _TOKEN_CACHE["access"] = tok
    return tok


def _get(path, params):
    token = _access_token()
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{BASE}{path}?{q}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def _f(d, *keys):
    """First non-empty field among keys, as float; None if absent."""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


@dataclass
class Metrics:
    symbol: str
    iv: float | None          # implied volatility index (decimal, 0.51 = 51%)
    iv_rank: float | None     # 0-100
    iv_pct: float | None      # 0-100
    beta: float | None
    liquidity: float | None   # rating (higher = more liquid)
    label: str = ""           # rich / cheap / mid


def market_metrics(symbols, rich_above=70, cheap_below=30) -> list[Metrics]:
    """IV rank + metrics for a list of symbols via /market-metrics."""
    data = _get("/market-metrics", {"symbols": ",".join(symbols)})
    items = (data.get("data") or {}).get("items") or []
    out = []
    for it in items:
        ivr = _f(it, "implied-volatility-index-rank", "tos-implied-volatility-index-rank")
        ivp = _f(it, "implied-volatility-percentile")
        # Tastytrade returns rank/percentile as 0-1 decimals; scale to 0-100.
        ivr = round(ivr * 100, 1) if ivr is not None and ivr <= 1.5 else ivr
        ivp = round(ivp * 100, 1) if ivp is not None and ivp <= 1.5 else ivp
        label = ("rich" if ivr is not None and ivr > rich_above else
                 "cheap" if ivr is not None and ivr < cheap_below else "mid")
        out.append(Metrics(
            symbol=it.get("symbol", "?"),
            iv=_f(it, "implied-volatility-index"),
            iv_rank=ivr, iv_pct=ivp,
            beta=_f(it, "beta"),
            liquidity=_f(it, "liquidity-rating", "liquidity-rank"),
            label=label,
        ))
    return out


def report(symbols, rich_above=70, cheap_below=30) -> str:
    try:
        rows = market_metrics(symbols, rich_above, cheap_below)
    except Exception as e:
        return f"IV RANK (Tastytrade) unavailable: {str(e)[:120]}"
    if not rows:
        return "IV RANK (Tastytrade): no data returned for watchlist."
    lines = ["IV RANK  [TOOL] Tastytrade /market-metrics (instant, no ramp)"]
    for m in sorted(rows, key=lambda r: (r.iv_rank is None, r.iv_rank or 0)):
        ivr = f"{m.iv_rank:>5.1f}" if m.iv_rank is not None else "  n/a"
        iv = f"{m.iv*100:>5.1f}%" if m.iv is not None else "   n/a"
        beta = f"{m.beta:>4.2f}" if m.beta is not None else " n/a"
        lines.append(f"   {m.symbol:<6} IVrank {ivr} [{m.label:<5}] "
                     f"IV {iv}  beta {beta}")
    lines.append("   → cheap IV = don't overpay for premium; rich IV = vol is "
                 "expensive. Context, NOT a gate.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or ["SPY", "QQQ", "NVDA", "AMD", "AAPL"]
    print(report(syms))
