"""Per-name headline fetcher — deterministic, free, no API key.

Pulls recent headlines per ticker from yfinance (free public feed). Returns
raw headlines for Claude Code to summarize via Firecrawl/UW MCP tools.
No Anthropic API call — Claude Code uses your existing subscription.

The summarization (sentiment / key drivers / position-impact flag) happens
in prompts/morning_brief.md, where Claude has access to Firecrawl + UW MCP
for richer context per name.
"""
from __future__ import annotations

import time
from datetime import date


def headlines(ticker, window_days=3):
    """Return recent headlines for a ticker. Empty list if none / on error."""
    import yfinance as yf

    cutoff = time.time() - window_days * 86400
    items = getattr(yf.Ticker(ticker), "news", []) or []
    out = []
    for it in items:
        ts = it.get("providerPublishTime", 0)
        if ts and ts < cutoff:
            continue
        out.append({
            "title": it.get("title", ""),
            "publisher": it.get("publisher", ""),
            "link": it.get("link", ""),
            "ts": ts,
        })
    return out


def for_names(tickers, window_days=3, asof=None):
    """Returns {ticker: [headlines]} for a list of names."""
    asof = asof or date.today().isoformat()
    return {t: headlines(t, window_days) for t in tickers}


if __name__ == "__main__":
    import sys
    for t in (sys.argv[1:] or ["SPY"]):
        hs = headlines(t)
        print(f"\n{t} — {len(hs)} headlines (last 3 days):")
        for h in hs[:5]:
            print(f"  - {h['title']} ({h['publisher']})")
