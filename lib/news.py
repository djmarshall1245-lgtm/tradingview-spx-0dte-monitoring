"""Per-name daily news analysis — the one paid piece. [YouTuber #2 / AI Pathways]

For each held name: pull recent headlines (yfinance .news, free), send them to
Claude via the Anthropic API, get back a short summary + sentiment + key
drivers + a flag for anything that hits a position. Cached per day in SQLite
so re-runs don't re-bill. Claude summarizes — it never says buy or sell.

Needs: ANTHROPIC_API_KEY env var, `anthropic` package, network.
Cost: ~$1/day depending on how many names. Everything else is free local compute.
"""
from __future__ import annotations

import json
import os
from datetime import date

from . import db as dbmod


def _headlines(ticker, window_days=3):
    import time
    import yfinance as yf

    cutoff = time.time() - window_days * 86400
    items = getattr(yf.Ticker(ticker), "news", []) or []
    out = []
    for it in items:
        ts = it.get("providerPublishTime", 0)
        if ts and ts < cutoff:
            continue
        out.append({"title": it.get("title", ""),
                    "publisher": it.get("publisher", ""),
                    "link": it.get("link", "")})
    return out


_PROMPT = """You are a markets analyst. Below are recent headlines for {ticker}.
Return STRICT JSON with keys: summary (<=2 sentences on what actually happened),
sentiment (positive|neutral|negative), key_drivers (list of short strings),
position_flag (true if anything here would materially move a holder's position).
Do NOT say buy or sell. Headlines:
{headlines}"""


def analyze(ticker, model="claude-opus-4-8", window_days=3, asof=None):
    asof = asof or date.today().isoformat()
    conn = dbmod.connect()
    cached = conn.execute(
        "SELECT * FROM news_analysis WHERE asof=? AND ticker=?", (asof, ticker)
    ).fetchone()
    if cached:
        conn.close()
        return dict(cached)

    heads = _headlines(ticker, window_days)
    if not heads:
        conn.close()
        return {"ticker": ticker, "summary": "no recent headlines",
                "sentiment": "neutral", "key_drivers": [], "position_flag": False}

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    text = "\n".join(f"- {h['title']} ({h['publisher']})" for h in heads)
    msg = client.messages.create(
        model=model, max_tokens=400,
        messages=[{"role": "user",
                   "content": _PROMPT.format(ticker=ticker, headlines=text)}])
    raw = msg.content[0].text.strip()
    try:
        parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception:
        parsed = {"summary": raw[:300], "sentiment": "neutral",
                  "key_drivers": [], "position_flag": False}

    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO news_analysis
               (asof,ticker,summary,sentiment,key_drivers,position_flag)
               VALUES (?,?,?,?,?,?)""",
            (asof, ticker, parsed.get("summary", ""), parsed.get("sentiment", "neutral"),
             json.dumps(parsed.get("key_drivers", [])),
             int(bool(parsed.get("position_flag", False)))))
    conn.close()
    parsed["ticker"] = ticker
    parsed["sources"] = [h["link"] for h in heads]
    return parsed
