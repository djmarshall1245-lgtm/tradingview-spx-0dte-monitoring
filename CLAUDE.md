# CLAUDE.md — SPX 0DTE Monitoring

Trading workspace for supervising a SPX/SPY 0DTE Pine Script on TradingView
Desktop. This file keeps Claude Code lean so it stays sharp during sessions.

## Keep-it-lean checklist

If Claude starts making sloppy, "dumber than usual" mistakes, it's almost
always one of these three — check them in order:

1. **Model — biggest lever.** Run `/model` and confirm you're on **Opus**
   (`claude-opus-4-8`) for real reasoning work. Sonnet 4.6 is a capability
   step down. Note: there is no `/FABLE` command — switch models only via
   `/model`.

2. **Session hygiene — run `/clear` between unrelated tasks.** File reads pile
   up in context (a long session can carry 40k+ tokens of stale read output).
   When context fills, Claude auto-compacts and summarizes away detail
   mid-task — that's a "gets dumber" event. Starting fresh avoids it. Use
   `/context` to check; if "Read results" is a large share, `/clear`.

3. **Prune skills/plugins.** Only keep skills relevant to trading. A large
   plugin catalog (e.g. ~100 `senior-*` / infra skills, ~30 `firecrawl-*`)
   costs ~12k+ tokens and adds decision noise on every turn. Disable plugins
   you don't use for this workflow.

## Trading safety rules — sourcing (apply to EVERY market briefing)

Confident output is not the same as verified output. Before any number or
claim is used for sizing a trade, it must be sourced. Follow these rules:

1. **Tag every fact with its source.** For each number or claim, mark:
   - `[TOOL]` — pulled live from a tool this session
   - `[STALE]` — from a cached/older tool result (include the timestamp)
   - `[MEMORY]` — model's own knowledge, NOT verified by a tool
2. **Re-pull live; never reuse cached files for the day's data.** If a tool
   fails, say so — do not fill the gap from memory.
3. **Show the source URL for any news/event** (IPOs, geopolitics, SKEW, etc.).
   If it wasn't pulled from the web this session, say so. No link → treat as
   `[MEMORY]`, not fact.
4. **End with a "DO NOT TRADE UNTIL YOU VERIFY" list** of everything tagged
   `[MEMORY]` or `[STALE]`.

Rule of thumb: numbers from tools = trust; stories from memory = verify.

### Briefing template (copy this structure every morning)

To trigger it, just say:
> "Give me my SPX 0DTE morning brief — pull my JC levels, institutional flow,
> and today's news + economic calendar with source links. Tag every fact
> [TOOL]/[STALE]/[MEMORY]."

```
SPX 0DTE MORNING BRIEF — <date>  |  pulled <time ET>

① OVERNIGHT / MACRO                       [TOOL] Firecrawl web (show URLs)
   /ES futures · VIX · 10Y yield · DXY · gold · crude — each w/ source URL
   Overnight high/low · gap vs prior close

② KEY LEVELS — from my JC (John Carter) script   [TOOL] TV pine_lines/labels
   study_filter: "JC"   (JC script must be visible on chart)
   Voodoo levels ..... pivot S/R, list high→low w/ price
   Fireline .......... ES futures HIGH  → overhead resistance
   Treeline .......... ES futures LOW   → support below
   → Is SPX above / below / inside the Fireline–Treeline range?
   → Nearest Voodoo above = target | below = trip-wire

③ INSTITUTIONAL FLOW & POSITIONING        [TOOL] Unusual Whales
   GEX regime (pos/neg gamma) + call wall / put wall strikes
   Dark pool prints ...... biggest levels + bull/bear lean
   Net options flow ...... premium into calls vs puts
   OI changes / max pain . where dealers are pinned

④ CATALYSTS                               [TOOL] Firecrawl web (show URLs)
   Economic calendar today . event + time ET + prior/consensus
   Earnings (overnight/AMC) . names that move SPX/sectors
   Upgrades / downgrades .... ticker, firm, old→new
   Geopolitical / headlines . one-liner + source URL

⑤ NEWS (top movers)                       [TOOL] Firecrawl web (show URLs)
   3-5 headlines, each with a clickable link
   Free sources: investing.com (news + econ calendar), reuters.com,
   apnews.com, cnbc.com, marketwatch.com, finance.yahoo.com,
   cmegroup.com FedWatch, sec.gov EDGAR

⑥ SUMMARY & BIAS
   Bias: BULLISH / BEARISH / NEUTRAL-CHOP
   Lean: favor CALLS / favor PUTS / flat until <level> breaks
   - Above Fireline (ES high) reclaimed → bullish, calls, target next Voodoo up
   - Below Treeline (ES low) lost      → bearish, puts, target next Voodoo down
   - Inside the range + neg gamma      → chop, stay flat until a break
   Upside target .... <level>   Downside trip-wire .... <level>

⑦ DO NOT TRADE UNTIL YOU VERIFY
   Claim | Tag [MEMORY]/[STALE]/[MISSING] | How to verify
```

A good brief has all NUMBERS/LEVELS tagged `[TOOL]`, all NEWS either
`[TOOL]`+URL or honestly flagged `[MEMORY]`, and a populated "DO NOT TRADE"
list. If the session has run long and facts show up "compacted", `/clear`
and re-pull.

## What is NOT the problem (verified, don't chase it)

- **MCP servers are fine.** Their tools load **on-demand** (~4k tokens total),
  not all upfront. The long `tradingview-mcp` / `unusualwhales` tool lists in
  `/mcp` do **not** bloat context. Leave the MCP servers connected.
- Servers showing `needs authentication` (robinhood, gmail, calendar, drive)
  are harmless if unused — authenticate them only when you actually need them.

## Diagnostics

- `/context` — token breakdown by category (model, skills, messages, reads).
- `/mcp` — MCP server connection status.
- `/model` — view / change the active model.
- `claude --debug` — see MCP startup errors if a server won't connect.

## MCP config

- `.mcp.json` defines the project's `tradingview` MCP server. The `args` path
  must point to the real `tradingview-mcp-jackson/src/server.js` on **this**
  machine. If it's wrong, the server fails to start every session.
- `.claude/launch.json` is a VS Code debugger format and is **not** read by
  Claude Code — it does nothing here.

## Setup reference (keep lean — do NOT re-bloat)

- **Superpowers** is the only skill pack kept (base system, required).
- **Do NOT reinstall** `engineering-skills`, `engineering-advanced-skills`, or
  `product-skills`. They were removed on purpose (~12k tokens + decision
  noise). Re-adding them is what made Claude "dumber". Need one? Install that
  single skill, not the whole pack.
- `tradingview` + `unusualwhales` MCP servers load tools on-demand (~4k) — keep
  them connected; they are not the bloat.
- Never paste a real token (GitHub PAT, etc.) into a CLAUDE.md — it is plain
  text. Use a shell env var instead.
