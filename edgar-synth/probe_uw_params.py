#!/usr/bin/env python3
"""Nail UW screener filter semantics: which param filters STOCK market-cap and
STOCK volume (vs options volume). Prints row COUNT per param combo so we can
see which one opens the universe to hundreds of names."""
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


HDR = {"Authorization": f"Bearer {token()}", "Accept": "application/json"}


def n(label, params):
    try:
        r = requests.get(UW, headers=HDR, params=params, timeout=30)
        if r.status_code != 200:
            print(f"{label:<42} HTTP {r.status_code}: {r.text[:90]}")
            return
        data = r.json().get("data", [])
        sample = [row.get("ticker") for row in data][:4]
        print(f"{label:<42} {len(data):>4} rows  {sample}")
    except Exception as e:
        print(f"{label:<42} ERR {e}")


MC = {"min_marketcap": 100000000, "max_marketcap": 10000000000}
n("A no params (limit100)", {"limit": 100})
n("B marketcap only", {**MC, "limit": 100})
n("C mc + min_volume=100000", {**MC, "min_volume": 100000, "limit": 100})
n("D mc + min_volume=0", {**MC, "min_volume": 0, "limit": 100})
n("E mc + min_stock_volume=100000", {**MC, "min_stock_volume": 100000, "limit": 100})
n("F mc + min_avg30_volume=100000", {**MC, "min_avg30_volume": 100000, "limit": 100})
n("G mc + min_stock_vol=100000", {**MC, "min_stock_vol": 100000, "limit": 100})
n("H mc only, limit=500", {**MC, "limit": 500})
n("I mc + issue_types=stock", {**MC, "issue_types[]": "Common Stock", "limit": 100})
