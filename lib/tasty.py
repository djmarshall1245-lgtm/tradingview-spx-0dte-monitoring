"""Tastytrade market-data client — DATA ONLY, no execution. [User-added]

NOTE — module is named `tasty.py` (not `tastytrade.py`) on purpose so it
does NOT shadow the installed `tastytrade` SDK. With the file previously
named `lib/tastytrade.py`, `from tastytrade import Session` resolved to
our own file instead of the SDK and failed with a misleading ImportError.

Tastytrade's API is built for options. The headline value here is
get_market_metrics: it returns IV RANK, IV percentile, implied vol, beta,
and liquidity per symbol INSTANTLY — no 20-day snapshot ramp needed. That's
a professional-grade IV-rank signal for the watchlist, today.

Uses the official `tastytrade` SDK (tastyware), which handles OAuth, the
15-min access-token auto-refresh, and SSL correctly. The SDK's OAuth
Session is `Session(provider_secret, refresh_token)` — OAuth-only, and it
does NOT take a client_id (the hand-rolled flow's client_id is why the raw
token call returned HTTP 400).

Secrets come from a gitignored .env (see .env.example):
    TASTYTRADE_CLIENT_SECRET    -> SDK provider_secret   (required)
    TASTYTRADE_REFRESH_TOKEN    -> SDK refresh_token      (required)
    TASTYTRADE_CLIENT_ID        -> optional / unused by the SDK OAuth flow

Execution is intentionally NOT implemented. This pulls data; orders stay
on Robinhood ****3232.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass


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
    """Return (provider_secret, refresh_token). client_id is optional/unused."""
    _load_env_file()
    secret = os.environ.get("TASTYTRADE_CLIENT_SECRET")
    refresh = os.environ.get("TASTYTRADE_REFRESH_TOKEN")
    missing = [n for n, v in [("TASTYTRADE_CLIENT_SECRET", secret),
                              ("TASTYTRADE_REFRESH_TOKEN", refresh)] if not v]
    if missing:
        raise RuntimeError(
            "Tastytrade creds missing: " + ", ".join(missing) +
            ". Put them in a local .env (gitignored) — see .env.example.")
    return secret, refresh


def _f(v):
    """Coerce a value (Decimal / str / None) to float, or None."""
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
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


async def _afetch(symbols):
    """Open an OAuth session, pull metrics, always close the httpx client."""
    from tastytrade import Session
    from tastytrade.metrics import get_market_metrics

    secret, refresh = _creds()
    session = Session(secret, refresh)          # provider_secret, refresh_token
    try:
        return await get_market_metrics(session, list(symbols))
    finally:
        close = getattr(session, "close", None)
        if close:
            res = close()
            if asyncio.iscoroutine(res):
                await res


def market_metrics(symbols, rich_above=70, cheap_below=30) -> list[Metrics]:
    """IV rank + metrics for a list of symbols via the official SDK."""
    try:
        raw = asyncio.run(_afetch(symbols))
    except ModuleNotFoundError:
        raise RuntimeError("tastytrade SDK not installed in this env — "
                           "run: pip install -r requirements.txt")
    out = []
    for it in raw:
        ivr = _f(getattr(it, "implied_volatility_index_rank", None))
        if ivr is None:
            ivr = _f(getattr(it, "tos_implied_volatility_index_rank", None))
        ivp = _f(getattr(it, "implied_volatility_percentile", None))
        # SDK returns rank/percentile as 0-1 decimals; scale to 0-100.
        ivr = round(ivr * 100, 1) if ivr is not None and ivr <= 1.5 else ivr
        ivp = round(ivp * 100, 1) if ivp is not None and ivp <= 1.5 else ivp
        label = ("rich" if ivr is not None and ivr > rich_above else
                 "cheap" if ivr is not None and ivr < cheap_below else "mid")
        liq = _f(getattr(it, "liquidity_rating", None))
        if liq is None:
            liq = _f(getattr(it, "liquidity_value", None))
        out.append(Metrics(
            symbol=getattr(it, "symbol", "?"),
            iv=_f(getattr(it, "implied_volatility_index", None)),
            iv_rank=ivr, iv_pct=ivp,
            beta=_f(getattr(it, "beta", None)),
            liquidity=liq,
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
    lines = ["IV RANK  [TOOL] Tastytrade get_market_metrics (instant, no ramp)"]
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
