#!/usr/bin/env python3
"""One-shot probe: find UW's stock-screener endpoint + field names so we can
replace the dead FMP screener in load_universe(). Reads the UW token from
~/.uw_credentials or the UW_API_TOKEN / UW_MCP_TOKEN env var. Prints which
candidate endpoint answers 200 and a sample row. Paste the output back.
"""
import json
import os
import sys
from pathlib import Path

import requests

UW = "https://api.unusualwhales.com"


def token():
    p = Path.home() / ".uw_credentials"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"') if "=" in line else line
    return os.environ.get("UW_API_TOKEN") or os.environ.get("UW_MCP_TOKEN") or ""


def main():
    tok = token()
    if not tok:
        sys.exit("no UW token (checked ~/.uw_credentials, UW_API_TOKEN, UW_MCP_TOKEN)")
    hdr = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    # candidate screener endpoints + a small market-cap/volume filter
    candidates = [
        ("/api/screener/stocks", {"min_marketcap": 100_000_000, "max_marketcap": 10_000_000_000, "min_volume": 100_000, "limit": 3}),
        ("/api/screener/stocks", {"market_cap_min": 100_000_000, "market_cap_max": 10_000_000_000, "limit": 3}),
        ("/api/stock/screener", {"limit": 3}),
        ("/api/screener/stock", {"limit": 3}),
    ]
    for path, params in candidates:
        try:
            r = requests.get(UW + path, headers=hdr, params=params, timeout=20)
        except requests.RequestException as e:
            print(f"\n--- {path} {params}\n  REQUEST ERROR: {e}")
            continue
        print(f"\n--- {path} {params}\n  HTTP {r.status_code}")
        if r.status_code == 200:
            body = r.json()
            rows = body.get("data", body) if isinstance(body, dict) else body
            print("  KEYS:", list(rows[0].keys()) if isinstance(rows, list) and rows else "(inspect below)")
            print(json.dumps(body, indent=2)[:1800])
            return
        else:
            print("  ", r.text[:200])
    print("\nNo candidate returned 200 — paste this whole output and we'll adjust the path.")


if __name__ == "__main__":
    main()
