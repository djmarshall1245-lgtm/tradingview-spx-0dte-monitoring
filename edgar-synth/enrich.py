"""Enrichment: Unusual Whales (universe + short + flow) + Alpaca (quotes).

Verified endpoints/fields:
  UW   /api/screener/stocks      -> ticker, full_name, marketcap (str),
                                    stock_volume, close (str), sector, is_index,
                                    issue_type. Server filters: min_marketcap,
                                    max_marketcap, min_volume, limit.
                                    (replaced FMP company-screener 2026-07-22)
  Alpaca /v2/stocks/{t}/trades/latest -> last trade price (see quote())
  UW   /api/shorts/{t}/data      -> fee_rate (string!), short_shares_available
  UW   /api/option-trades/flow-alerts -> ticker, type, total_premium (string!),
                                         total_size, volume_oi_ratio, created_at
UW numeric fields arrive as strings — always _to_float().
"""
import os
import json
import time
import logging
from pathlib import Path

import requests

log = logging.getLogger("enrich")
UW_BASE = "https://api.unusualwhales.com"
UNIVERSE_CACHE = Path("universe.json")


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _alpaca_headers():
    return {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", ""),
            "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET", "")}


def _uw_token():
    """~/.uw_credentials first, then UW_API_TOKEN / UW_MCP_TOKEN env vars.
    The env fallback means a stale/missing credentials file can't silently
    blind edgar-synth when the working token is already in the shell (the
    2026-07-22 failure mode)."""
    p = Path.home() / ".uw_credentials"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if "TOKEN" in k.upper() or "KEY" in k.upper():
                    return v.strip().strip('"')
            else:
                return line  # raw token on its own line
    return os.environ.get("UW_API_TOKEN") or os.environ.get("UW_MCP_TOKEN") or ""


# ---- universe ---------------------------------------------------------------
def _parse_screener(rows, min_volume=0):
    """UW /api/screener/stocks rows -> {ticker: {companyName, marketCap, price,
    volume}}. Drops indices, ETFs and funds (we trade single-name equities) and
    names whose avg-30d volume is below min_volume (STOCK-volume filter done
    client-side — UW's min_volume param filters OPTIONS volume, confirmed
    2026-07-22, which is why it pinned the universe to 1 name)."""
    universe = {}
    for row in rows:
        if row.get("is_index"):
            continue
        itype = str(row.get("issue_type", "")).lower()
        if "etf" in itype or "fund" in itype:
            continue
        vol = _to_float(row.get("avg30_volume")) or _to_float(row.get("stock_volume"))
        if vol < min_volume:
            continue
        t = str(row.get("ticker", "")).upper()
        if not t:
            continue
        universe[t] = {
            "companyName": row.get("full_name", ""),
            "marketCap": _to_float(row.get("marketcap")),
            "price": _to_float(row.get("close")),
            "volume": vol,
        }
    return universe


# UW screener caps at 500 rows/call and ignores page= (probed 2026-07-22), so
# a single call can't return the full universe. We partition the market-cap
# range into buckets each expected to hold < 500 names and merge them. Finer at
# the low end where small-caps cluster. A bucket returning exactly 500 is likely
# truncated (logged) — subdivide that range if it happens.
_MC_LADDER = [100e6, 175e6, 275e6, 400e6, 550e6, 750e6, 1e9, 1.4e9,
              2e9, 3e9, 4.5e9, 7e9, 10e9, 20e9, 50e9, 100e9]


def load_universe(cfg):
    """{ticker: {companyName, marketCap, price, volume}} — cached to disk daily.

    Source: Unusual Whales /api/screener/stocks (replaced FMP 2026-07-22).
    Refresh needs a UW token (~/.uw_credentials or UW_API_TOKEN env). No token
    and stale cache -> use the cache; no token and no cache -> hard stop.
    """
    u = cfg["universe"]
    tok = _uw_token()
    if UNIVERSE_CACHE.exists():
        age_h = (time.time() - UNIVERSE_CACHE.stat().st_mtime) / 3600
        if age_h < u.get("refresh_hours", 24):
            return json.loads(UNIVERSE_CACHE.read_text())
        if not tok:
            log.warning("universe.json is %.0fh old and no UW token to refresh "
                        "— using stale cache.", age_h)
            return json.loads(UNIVERSE_CACHE.read_text())
    if not tok:
        raise SystemExit("No universe.json and no UW token (~/.uw_credentials "
                         "or UW_API_TOKEN env). Cannot build the universe.")
    lo, hi = float(u["market_cap_min"]), float(u["market_cap_max"])
    edges = sorted({lo, hi} | {e for e in _MC_LADDER if lo < e < hi})
    buckets = list(zip(edges[:-1], edges[1:]))
    min_vol = float(u.get("volume_min", 0))
    limit = int(u.get("limit", 5000))
    hdr = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    universe, truncated = {}, []
    for a, b in buckets:
        r = requests.get(f"{UW_BASE}/api/screener/stocks",
                         params={"min_marketcap": int(a), "max_marketcap": int(b), "limit": 500},
                         headers=hdr, timeout=30)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if len(rows) >= 500:                      # bucket hit the cap — may be missing names
            truncated.append((int(a), int(b)))
        universe.update(_parse_screener(rows, min_vol))
        if len(universe) >= limit:
            break
    if truncated:
        log.warning("UW mc-buckets hit the 500-row cap (may miss names) — subdivide: %s",
                    truncated)
    if universe:
        UNIVERSE_CACHE.write_text(json.dumps(universe))
        log.info("universe refreshed via UW: %d names across %d mc-buckets",
                 len(universe), len(buckets))
    else:
        log.warning("UW screener returned 0 usable names — keeping existing cache")
        if UNIVERSE_CACHE.exists():
            return json.loads(UNIVERSE_CACHE.read_text())
    return universe


def quote(ticker):
    """Last trade via Alpaca data API (IEX feed). Returns (price, ts) or (None, None)."""
    try:
        r = requests.get(f"https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest",
                         params={"feed": "iex"}, headers=_alpaca_headers(), timeout=10)
        r.raise_for_status()
        t = r.json().get("trade") or {}
        return t.get("p"), t.get("t")
    except requests.RequestException as e:
        log.warning("quote failed %s: %s", ticker, e)
    return None, None


# ---- Unusual Whales ---------------------------------------------------------
class UWClient:
    def __init__(self, ttl_sec=900):
        self.token = _uw_token()
        self.ttl = ttl_sec
        self._cache = {}
        if not self.token:
            log.warning("no UW token found at ~/.uw_credentials — short/flow factors will be 0")

    def _get(self, path, params=None):
        if not self.token:
            return None
        key = (path, tuple(sorted((params or {}).items())))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1]
        try:
            r = requests.get(f"{UW_BASE}{path}", params=params or {},
                             headers={"Authorization": f"Bearer {self.token}",
                                      "Accept": "application/json"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            self._cache[key] = (time.time(), data)
            return data
        except requests.RequestException as e:
            log.warning("UW %s failed: %s", path, e)
            return None

    def short_data(self, ticker):
        """Returns {fee_rate, short_shares_available} floats, or zeros."""
        data = self._get(f"/api/shorts/{ticker}/data")
        rows = (data or {}).get("data") or []
        latest = rows[-1] if isinstance(rows, list) and rows else (rows if isinstance(rows, dict) else {})
        return {
            "fee_rate": _to_float(latest.get("fee_rate")),
            "short_shares_available": _to_float(latest.get("short_shares_available")),
        }

    def flow_summary(self, ticker):
        """Recent flow-alerts skew for ticker: premium-weighted call vs put."""
        data = self._get("/api/option-trades/flow-alerts",
                         params={"ticker_symbol": ticker, "limit": 50})
        alerts = (data or {}).get("data") or []
        call_prem = put_prem = 0.0
        for a in alerts:
            prem = _to_float(a.get("total_premium"))
            if a.get("type") == "call":
                call_prem += prem
            elif a.get("type") == "put":
                put_prem += prem
        total = call_prem + put_prem
        skew = (call_prem - put_prem) / total if total > 0 else 0.0  # -1..+1
        return {"call_premium": call_prem, "put_premium": put_prem,
                "skew": skew, "alert_count": len(alerts)}
