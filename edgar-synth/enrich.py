"""Enrichment: FMP (universe, quotes) + Unusual Whales (short data, flow alerts).

Verified endpoints/fields:
  FMP  /stable/company-screener  -> symbol, companyName, marketCap, price, volume
  FMP  /stable/quote             -> symbol, price, timestamp
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
FMP_BASE = "https://financialmodelingprep.com/stable"
UW_BASE = "https://api.unusualwhales.com"
UNIVERSE_CACHE = Path("universe.json")


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmp_key():
    return os.environ.get("FMP_API_KEY", "")


def _alpaca_headers():
    return {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", ""),
            "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET", "")}


def _uw_token():
    p = Path.home() / ".uw_credentials"
    if not p.exists():
        return ""
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
    return ""


# ---- universe ---------------------------------------------------------------
def load_universe(cfg):
    """{ticker: {companyName, marketCap, price, volume}} — cached to disk daily.

    No FMP_API_KEY (FMP is MCP-only on this machine): use the cache at any
    age. Refresh it via a Claude session (FMP MCP screener -> universe.json).
    """
    u = cfg["universe"]
    if UNIVERSE_CACHE.exists():
        age_h = (time.time() - UNIVERSE_CACHE.stat().st_mtime) / 3600
        if age_h < u.get("refresh_hours", 24):
            return json.loads(UNIVERSE_CACHE.read_text())
        if not _fmp_key():
            log.warning("universe.json is %.0fh old and no FMP_API_KEY to refresh "
                        "— using stale cache. Refresh via Claude (FMP MCP).", age_h)
            return json.loads(UNIVERSE_CACHE.read_text())
    if not _fmp_key():
        raise SystemExit("No universe.json and no FMP_API_KEY. Generate universe.json "
                         "via a Claude session (FMP MCP company screener).")
    params = {
        "marketCapMoreThan": u["market_cap_min"],
        "marketCapLowerThan": u["market_cap_max"],
        "volumeMoreThan": u["volume_min"],
        "country": u.get("country", "US"),
        "isActivelyTrading": "true", "isEtf": "false", "isFund": "false",
        "limit": u.get("limit", 3000),
        "apikey": _fmp_key(),
    }
    r = requests.get(f"{FMP_BASE}/company-screener", params=params, timeout=30)
    r.raise_for_status()
    universe = {row["symbol"].upper(): {
        "companyName": row.get("companyName", ""),
        "marketCap": row.get("marketCap", 0),
        "price": row.get("price", 0),
        "volume": row.get("volume", 0),
    } for row in r.json()}
    UNIVERSE_CACHE.write_text(json.dumps(universe))
    log.info("universe refreshed: %d names", len(universe))
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
