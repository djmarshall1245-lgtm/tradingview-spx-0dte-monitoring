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

```
SPX 0DTE PRE-TRADE BRIEFING — <date>

SESSION CLOSE / LEVELS
  Open / Close / Session move — each line tagged [TOOL]/[STALE]/[MEMORY]
  with the tool name + pull time (e.g. [TOOL] TV quote_get CBOE:SPX, 9:30 ET).

GEX REGIME: <POSITIVE/NEGATIVE> GAMMA (<net>)  [TOOL] UW get_greek_exposure_by_strike
  Strike | Net GEX | Role (call wall / pivot / put accel / put wall) | Source tag

MAX PAIN: <level>  [TOOL] UW get_max_pain

5-BULLET SUMMARY  (bias / upside target / downside trip-wire / chop zone / watch)
  — every bullet carries a source tag; news lines need a URL or get [MEMORY].

DO NOT TRADE UNTIL YOU VERIFY
  Claim | Tag ([MEMORY]/[STALE]/[MISSING]) | Action to verify
```

A good briefing has all NUMBERS tagged `[TOOL]`, all NEWS either `[TOOL]`+URL
or honestly flagged `[MEMORY]`, and a populated "DO NOT TRADE" list. If the
session has run long and facts show up "compacted", run `/clear` and re-pull.

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
