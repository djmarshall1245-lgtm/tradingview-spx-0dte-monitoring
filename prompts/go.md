---
name: go
description: One-paste daily launcher — runs startup checks + python brief + MCP enrichment in a single Claude Code session
version: 1.0.0
metadata:
  hermes:
    tags: [trading, launcher, daily, premarket]
    category: trading
    requires_tools: [unusualwhales, firecrawl, tradingview, robinhood-trading]
---

# GO — the one-paste daily launcher

This is the ONLY thing you paste each morning. Works entirely inside Claude
Code — Claude runs the Python itself (via the project venv) AND does the
live enrichment, so you never switch to Mac Terminal for the routine.

Paste everything in the block below into Claude Code from inside
`~/tradingview-spx-0dte-monitoring`.

---

```
RUN MY FULL MORNING SEQUENCE. Do every step in order, no skipping.

STEP 1 — STARTUP DISCIPLINE (from CLAUDE.md):
  a. Read strategy/strategy.yaml, strategy/goal.yaml, config.yaml. Recite
     premium band, stop %, flow ratio, max positions. THE FILE WINS over
     any memory.
  b. Run /mcp. Confirm all 4 connected: tradingview, unusualwhales,
     firecrawl, robinhood-trading. If any missing/unauth -> HALT, tell me.
  c. Anchor today: run `date`. State "Today is <weekday> <YYYY-MM-DD>."
     Every date you output must carry its verified weekday.

STEP 2 — RUN THE PYTHON BRIEF YOURSELF:
  Run this exact command (use the project venv — plain `python` will fail):
     ./.venv/bin/python run.py --snapshot --score --brief
  If ./.venv/bin/python doesn't exist, fall back to:
     ./.venv/bin/python3 run.py --snapshot --score --brief
  Capture the full output. This gives you macro score, expectancy, book
  health, condition alerts, and raw headlines for all 12 names.

STEP 3 — ENRICH (follow prompts/morning_brief.md exactly):
  Apply ALL of its rules: source-or-omit, sanity-check dates, flow vs
  positional staleness split, mandatory ⑦ verify list, mandatory ⑧ tool
  receipt. For ④ news: Firecrawl the most material story per name (or
  [NO DATA]). For ⑤ flow: if pre-open, "NO LIVE FLOW — awaiting open";
  pull positional data (max pain/GEX/OI) as [CURRENT as of last close].
  VERIFY any breaking headline via Firecrawl before narrating it.

STEP 4 — DELIVER:
  The full brief ①-⑧ exactly as prompts/morning_brief.md specifies.
  End with: "No trade calls — that's the trade desk's job, with your GO."

Do NOT propose or place any trade in this sequence. This is OBSERVE only.
When a setup forms later, I'll paste prompts/trade_desk.md separately.
```

---

## If you'd rather split it (optional)

The Mac-Terminal-only version of step 2, if you ever want to run data
capture without opening Claude Code:

```bash
cd ~/tradingview-spx-0dte-monitoring && source .venv/bin/activate && python run.py --snapshot --score --brief
```

But the one-paste block above is the everyday path — it does this for you.
