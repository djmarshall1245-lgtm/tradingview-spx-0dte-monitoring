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

② KEY LEVELS                              [TOOL] TradingView  (two pulls)
   A) Voodoo levels (pivot S/R) — from my chart script:
      data_get_pine_labels, study_filter: "AR SQUEEZE"  (script visible on chart)
      List R3..PP..S3 high→low w/ price. These ARE on the chart.
   B) Fireline / Treeline = /ES futures session high/low (NOT pivots, NOT labels —
      the AR Squeeze script does NOT plot these):
      data_get_ohlcv on ES1! (summary: true), then:
      🔥 Fireline = ES High → resistance above
      🌲 Treeline = ES Low  → support below
      Note the ES→SPX offset (ES ~5-10 pts above SPX, fluctuates). Convert to SPX.
      Default window = today's regular session; say "full Globex" for overnight.
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

## Live Trade Desk (intraday — 3 subagents)

Token-lean multi-agent setup. Run **1-2× a day when a signal is setting up** —
NOT continuously. The two data subagents isolate the heavy pulls (their big
payloads stay out of the main context); the decision-agent is a cheap
reasoning gate. The morning brief stays separate — it's the once-daily
strategic layer; this is the tactical at-signal layer.

**Trigger:** "Run my trade desk on the current setup."

Sequence the main session follows:
1. **quant-agent** → chart snapshot: SIGNAL (TREND/SCALP/EARLY/WATCH),
   CONFLUENCE x/6, Voodoo levels, Fireline/Treeline (ES1!), TIME window. Reads
   the AR Squeeze dashboard; trusts the script.
2. **flow-agent**, pass it the SIGNAL → independent UW verdict:
   CONFIRM / CONTRADICT / MIXED + GEX regime (pos gamma = fade extremes, neg =
   go with breaks).
3. **decision-agent**, pass it the Quant snapshot + Flow verdict → applies the
   risk rules and returns the gate result + trade plan:
   - Hard stop = **−50% of premium paid** (pay $1,000 → cut at $500); also exit
     on chart invalidation (signal flip, VWAP lost, MON EXIT, 3:30 close-out).
   - **Daily cap = 2 SPX trades. Two losses = done for the day.**
   - Conviction: **TREND** = full; **SCALP** = only if CONFLUENCE ≥3 and Flow
     not CONTRADICT; **EARLY** = prep only, never a live entry.
   - Time: entries only 9:45–2:30 ET, skip lunch 12–1, none after 2:30.
   - Verdict: **APPROVE** (all gates pass) / **APPROVE WITH CONCERNS** (mixed,
     smaller) / **REJECT** (Flow contradicts, confluence <3, EARLY-only, wrong
     time, or cap hit). Tag any [MEMORY] assumption.
   - If approved → TRADE PLAN: CALL/PUT · 0DTE strike · entry trigger · TP =
     next Voodoo (R1/R2 calls, S1/S2 puts) · stop −50% · "trade #_ of 2 today."

Subagent files live in `.claude/agents/` (quant-agent, flow-agent,
decision-agent). They load on-demand — they do not bloat every-session context.

## Robinhood MCP (official agentic trading)

Server: `robinhood-trading` → `https://agent.robinhood.com/mcp/trading`
(official, OAuth via `/mcp`). Use it for the STOCK side — NOT SPX 0DTE.

Scope & safety:
- **Equities + SINGLE-LEG options** (verified via the live tool list — the
  "equities only" press line is outdated). No spreads/multi-leg via MCP. Crypto
  read-only. So it CAN execute SPX/SPY single-leg 0DTE calls/puts.
- It can **read all accounts** but can only **trade in the agentic sub-account**
  (••••3232). Keep that sandbox funded with **risk capital only**.
- **Per-trade manual approval = ON.** Never enable auto-execute — an LLM with a
  live trade button is the one thing to avoid. The desk decides, you approve,
  THEN it places.
- Kill switches: `/mcp` → "Clear authentication" revokes access; the RH app has
  an instant-shutoff.

Read-only dashboard trigger:
> "Read my Robinhood main account: portfolio health check — concentration risk,
> biggest losers, margin/cash balance, positions bleeding or near-worthless.
> Read-only, no trades. Tag [TOOL]."

Managing existing option positions (e.g. into expiry): pull the live mark +
P&L% vs what was paid, cross-check UW flow/GEX, then apply the **−50% premium
stop** — CUT if at/below −50%, factor theta and distance to break-even.

### Single-leg 0DTE execution (SPX/SPY calls & puts)

Runs ONLY after the decision-agent APPROVES. Sandbox ••••3232, manual approval,
never auto-fire. This is the execution arm of the trade desk.

PICK THE CONTRACT:
1. `get_option_chains` on SPX (or SPXW) for today's 0DTE expiry. If Robinhood
   doesn't list SPX index options on the account, fall back to **SPY** (≈1/10
   SPX) — confirm with `get_option_chains` SPY.
2. Strike = **ATM to 1-strike ITM** in the signal's direction (target delta
   ~0.45–0.55) — moves with the underlying, NOT a far-OTM lotto. CALL at/above
   spot, PUT at/below.
3. `get_option_quotes`: check **bid/ask spread + delta + volume.** Wide/illiquid
   → use SPY or skip. Don't pay a fat spread on 0DTE.

PLACE IT (LIMIT, never market):
4. Limit price = **mid** (or mid + 1 tick to fill). A market order on 0DTE gets
   slipped.
5. `review_option_order` → preview cost, buying power, fees. Show me.
6. **MANUAL APPROVAL**, then `place_option_order` (single-leg, ••••3232).
7. Size = my call (confirm contracts); per-trade risk is capped by the −50%
   stop, not a fixed $.

MANAGE & EXIT (every close also = review → approve → place):
8. **TP** = next Voodoo (R1/R2 calls, S1/S2 puts) → sell-to-close limit at target.
9. **Hard stop** = −50% of premium paid → sell-to-close immediately if hit.
10. **Chart invalidation** (signal flip, VWAP lost, MON EXIT) or **3:30 ET** → exit.
11. Log it as "trade #_ of 2 today." Two losses = done.

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
