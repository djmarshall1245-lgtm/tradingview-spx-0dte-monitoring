#!/usr/bin/env python3
"""Last unknown: does the UW screener return >500 in one call, or must we page?
Tests big limits and whether `page` advances to DIFFERENT names. No min_volume
(that filters options volume — confirmed 2026-07-22)."""
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
MC = {"min_marketcap": 100000000, "max_marketcap": 10000000000}


def go(label, params):
    try:
        r = requests.get(UW, headers=HDR, params=params, timeout=45)
        if r.status_code != 200:
            print(f"{label:<28} HTTP {r.status_code}")
            return None
        data = r.json().get("data", [])
        first = data[0].get("ticker") if data else None
        last = data[-1].get("ticker") if data else None
        print(f"{label:<28} {len(data):>4} rows  first={first} last={last}")
        return data
    except Exception as e:
        print(f"{label:<28} ERR {e}")
        return None


print("== how many in one call ==")
go("limit=1000", {**MC, "limit": 1000})
go("limit=2000", {**MC, "limit": 2000})
go("limit=5000", {**MC, "limit": 5000})
print("\n== does page= advance? (limit=500) ==")
p0 = go("page=0", {**MC, "limit": 500, "page": 0})
p1 = go("page=1", {**MC, "limit": 500, "page": 1})
if p0 and p1:
    s0 = {r.get("ticker") for r in p0}
    s1 = {r.get("ticker") for r in p1}
    overlap = len(s0 & s1)
    print(f"\npage0∩page1 overlap = {overlap}  "
          f"({'PAGING WORKS — disjoint' if overlap == 0 else 'SAME PAGE — page param ignored'})")
