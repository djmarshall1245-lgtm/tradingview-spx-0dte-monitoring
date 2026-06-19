"""Per-name headline fetcher — deterministic, free, no API key.

Pulls recent headlines per ticker from yfinance (free public feed). Returns
raw headlines for Claude Code to summarize via Firecrawl/UW MCP tools.
No Anthropic API call — Claude Code uses your existing subscription.

The summarization (sentiment / key drivers / position-impact flag) happens
in prompts/morning_brief.md, where Claude has access to Firecrawl + UW MCP
for richer context per name.

Handles BOTH the legacy flat yfinance .news schema and the newer nested
schema (fields under "content" subdict, pubDate as ISO string instead of
providerPublishTime as unix timestamp).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone


def _parse_ts(item):
    """Extract a unix timestamp from either old or new yfinance .news shape."""
    # legacy: top-level providerPublishTime (unix seconds)
    ts = item.get("providerPublishTime")
    if ts:
        return float(ts)
    # newer: content.pubDate as ISO 8601 string
    content = item.get("content") or {}
    iso = content.get("pubDate") or content.get("displayTime")
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            return 0.0
    return 0.0


def _parse_title(item):
    return item.get("title") or (item.get("content") or {}).get("title", "")


def _parse_publisher(item):
    if item.get("publisher"):
        return item["publisher"]
    content = item.get("content") or {}
    provider = content.get("provider") or {}
    return provider.get("displayName", "")


def _parse_link(item):
    if item.get("link"):
        return item["link"]
    content = item.get("content") or {}
    for key in ("clickThroughUrl", "canonicalUrl"):
        url_obj = content.get(key) or {}
        url = url_obj.get("url") if isinstance(url_obj, dict) else url_obj
        if url:
            return url
    return ""


def headlines(ticker, window_days=3):
    """Return recent headlines for a ticker. Empty list if none / on error."""
    import yfinance as yf

    cutoff = time.time() - window_days * 86400
    items = getattr(yf.Ticker(ticker), "news", []) or []
    out = []
    for it in items:
        ts = _parse_ts(it)
        if ts and ts < cutoff:
            continue
        title = _parse_title(it)
        if not title:
            continue                          # skip empty/malformed records
        out.append({
            "title": title,
            "publisher": _parse_publisher(it),
            "link": _parse_link(it),
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
            if h["link"]:
                print(f"    {h['link']}")
