#!/usr/bin/env python3
"""Measure UW screener paging: how many rows come back at various limits, and
whether a page/offset param advances results. Tells us the real cap + how to
paginate to the full universe. Reads token like enrich._uw_token()."""
import os
from pathlib import Path
import requests

UW = "https://api.unusualwhales.com/api/screener/stocks"


def token():
    p = Path.home() / ".uw_credentials"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"') if "=" in line else line
    return os.environ.get("UW_API_TOKEN") or os.environ.get("UW_MCP_TOKEN") or ""


def count(params):
    hdr = {"Authorization": f"Bearer {token()}", "Accept": "application/json"}
    try:
        r = requests.get(UW, headers=hdr, params=params, timeout=30)
        if r.status_code != 200:
            return f"HTTP {r.status_code}: {r.text[:120]}"
        data = r.json().get("data", [])
        tickers = [row.get("ticker") for row in data][:5]
        return f"{len(data)} rows  sample={tickers}"
    except Exception as e:
        return f"ERR {e}"


base = {"min_marketcap": 100000000, "max_marketcap": 10000000000, "min_volume": 100000}
print("== vary limit ==")
for lim in (10, 50, 100, 250, 500, 1000, 5000):
    print(f"limit={lim:<5} -> {count({**base, 'limit': lim})}")
print("\n== no limit param ==")
print("(none)      ->", count(base))
print("\n== paging test (limit=100, page 0/1/2) ==")
for pg in (0, 1, 2):
    print(f"page={pg} -> {count({**base, 'limit': 100, 'page': pg})}")
