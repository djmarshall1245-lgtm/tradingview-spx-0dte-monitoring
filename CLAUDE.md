# CLAUDE.md — SPX 0DTE Monitoring

Trading workspace for supervising a SPX/SPY 0DTE Pine Script on TradingView
Desktop. This file keeps Claude Code lean so it stays sharp during sessions.

## FILE DELIVERY RULE — always hand back the pull command

The cloud session creates + pushes files; the user uses them on their **Mac
terminal**. A new file is useless until it's pulled down. So: ANYTIME I create
and push a new file (or any commit the user needs locally), I **end that turn
with the paste-safe pull command — automatically, without being asked**:

    cd ~/tradingview-spx-0dte-monitoring && git pull origin <current-branch>

(substitute the real branch — currently `claude/plce-XFleD`; no `#` comments, no
slash commands — it's pasted into zsh, not the Claude app.) Then add a one-line
verify, e.g. `ls -1 <path> && head -12 <path>`.

Conflict caveat: if the pull reports a merge conflict or "local changes would be
overwritten," STOP — have the user paste the exact error, then use
`git stash` → pull → `git stash drop` (NEVER `git stash pop`). The user should
never have to ask "how do I pull this."

## START-OF-SESSION RULE — read the YAML first, ALWAYS

Before answering ANY trading question, proposing ANY setup, or summarizing
ANY rule, **read these two files and treat them as the single source of
truth**:

  1. `strategy/strategy.yaml`  ← current playbook (gates, exits, premium band)
  2. `strategy/goal.yaml`      ← objective, drawdown limits, account floor

If your memory/recap disagrees with what's on disk, **the file wins.**
Cite the actual values back to me before proposing anything (premium band,
stop %, flow ratio, max positions). This is why the spine is versioned —
it exists so verbal drift can't override the rules.

Also read `config.yaml` for the watchlist + sector map before any
concentration check. Do not invent sub-rules ("ASK-side", "ascending fills",
"3+ alerts") that aren't in `strategy.yaml`. New rules go in via the Friday
loop with my GO, never via a recap.

## START-OF-SESSION RULE — verify MCP tools BEFORE any trading action

Right after reading the YAML files, run `/mcp` and confirm all five of
these servers show **connected** (not `needs authentication`, not missing):

  1. `tradingview`        — chart reads (TradingView MCP)
  2. `unusualwhales`      — institutional flow, GEX, dark pool, max pain
  3. `firecrawl`          — news enrichment per held name
  4. `robinhood-trading`  — order preview + placement (sub ****3232)
  5. `FMP`                — deterministic quote layer: index prints, VIX,
                            SPY, market hours (backstops brief section ①)
  6. `alpaca`             — market data #2: real-time quotes, intraday bars,
                            options chains. DATA-ONLY by config
                            (`ALPACA_TOOLSETS=data` in `.mcp.json`) — it has
                            NO order tools; Robinhood stays the only
                            execution arm.

FMP plan-tier quirks (verified 2026-07-01): `^SPX` is BLOCKED on the
current plan — use `^GSPC` (same index) via the indexes tool, or SPY as
the ETF proxy. FMP has no `ES1!` — Fireline/Treeline stays on TradingView.

Alpaca plan quirks (verified 2026-07-01): INDEX data is NOT authorized on
the current plan ("not authorized for index data" on SPX) — index prints
come from FMP (^GSPC). Alpaca's lane: stocks/ETFs (SPY), options chains,
intraday bars, news. Stock feed is IEX (not full SIP) — fine for
snapshots/levels; the Robinhood order preview is the acted-on bid/ask.

If ANY are missing or unauthenticated, HALT and tell me which:

> "MCP CHECK FAILED — <server> is <missing | needs authentication>.
>  Cannot proceed with morning brief / trade desk until fixed."

Do not try to substitute one tool for another (no "I'll use web search
instead of Firecrawl") and do not present a brief that silently lacks
flow or news data. A trading system reporting partial data without saying
so is the false-confidence failure mode — same class as the stale UW
tables on 2026-06-20.

Tool-loading is lazy by design (saves ~4k tokens/session), so connected
servers won't show up in context until a prompt triggers them. That's
fine. The /mcp check confirms they're AVAILABLE — the prompts handle
loading them when needed (`requires_tools` in each SKILL.md frontmatter).

## DATE & TIME DISCIPLINE — applies to EVERY output, no exceptions

Every date you state must be paired with the CORRECT day-of-week, computed
from the calendar — never guessed. Examples of the failure this prevents
(observed in this repo):

- "Expires Monday (June 26)" — WRONG. June 26, 2026 is a Friday. Monday
  is June 22. That mistake compressed a 5-trading-day decision window
  into 1 day = forced panic.
- "Wednesday 6/25, Tuesday 6/24" — WRONG weekdays for those dates. PCE
  on Wednesday when the calendar actually placed it Friday = positioning
  for the wrong day.

RULES:
1. Run `date` in the terminal (or use a tool) to anchor "today" before
   ANY output that references dates. State today in the output: "Today
   is <weekday> <YYYY-MM-DD>."
2. Any date you mention must include the verified day-of-week:
   "expires Fri 2026-06-26 (5 trading days)" — not "expires Monday."
3. If unsure of a day-of-week, say "<date — day to verify>" and don't
   guess. Better to admit uncertainty than to ship a wrong day.
4. After writing, self-check: does each stated weekday match the date?
   If any mismatch, the output is INVALID and must be corrected before
   you ship it. This is the same class of failure as fabricating a price
   — wrong dates lead to wrong decisions on real money.

This rule outranks anything in a SKILL.md prompt and applies to portfolio
read-outs, briefs, trade proposals, weekend recaps — every output.

## DATA BEATS NARRATIVE — hard numbers outrank scraped headlines

When deterministic data (overnight tells in section ⓪, lib/ pulls,
Unusual Whales positional numbers, live quotes) DISAGREES with a scraped
news headline or narrative, **the numbers win.** Verify the story against
the data before acting on it. If they conflict and you can't resolve the
conflict, REDUCE conviction or stand down — never trade the louder/scarier
story over the index print.

Observed live (2026-06-23): a Firecrawl headline claimed "KOSPI crashed
~10%, global tech rout," but the live index data showed KOSPI +0.69%,
Nikkei +1.55%, DAX +0.62% — only US futures were red. It was a
US-specific selloff, not a global rout. The data caught the narrative.
A headline is a [MEMORY]-class claim until the numbers confirm it.

## Keep-it-lean checklist

If Claude starts making sloppy, "dumber than usual" mistakes, it's almost
always one of these three — check them in order:

1. **Model — biggest lever.** Run `/model` and confirm you're on **Fable 5**
   (`/model claude-fable-5`) for real reasoning work — it's Anthropic's
   Claude 5 tier, ABOVE Opus. Fallback order: Fable 5 → Opus
   (`claude-opus-4-8`). Sonnet 4.6 is a capability step down. Switch models
   only via `/model` — there is no `/FABLE` slash command.

   **Mac CLI is PINNED at Claude Code 2.1.108 — do NOT update it.**
   Versions after 2.1.108 ship binaries that crash this Intel Mac with
   `zsh: illegal hardware instruction` (verified 2026-07-01: both the npm
   2.1.198 build AND the official `install.sh` native binary crashed;
   2.1.108 works). `DISABLE_AUTOUPDATER=1` is set in `~/.zshrc` on purpose
   — leave it. Model routing is server-side, so 2.1.108 still runs Fable 5
   fine. To retest Intel support later: temporarily reinstall latest via
   npm; if it still crashes, `npm install -g @anthropic-ai/claude-code@2.1.108`
   to restore.

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

① OVERNIGHT / MACRO                       [TOOL] FMP + Firecrawl web (URLs)
   Hard prints from FMP first (deterministic, no scraping): S&P 500 = ^GSPC
   (NOT ^SPX — plan-blocked) · ^VIX · SPY · market open/closed (marketHours).
   /ES futures · 10Y yield · DXY · gold · crude — FMP has no ES1!; pull these
   via Firecrawl w/ source URL (or FMP commodity/forex endpoints if they work).
   Overnight high/low · gap vs prior close
   → RISK read: oil + VIX + /ES direction together. Oil DOWN + VIX DOWN + ES UP
     = risk-ON; the reverse = risk-OFF. On a news-driven gap, say whether it's
     HOLDING or FADING (gaps fade — don't assume the overnight move sticks).
   → Paste the day's macro CONTEXT here (event/deal/Fed) — keep it out of the
     saved template so it never goes stale.

② KEY LEVELS                              [TOOL] TradingView  (two pulls)
   A) Voodoo levels (pivot S/R) — from my chart script:
      data_get_pine_labels, study_filter: "AR SQUEEZE"  (script visible on chart)
      List R3..PP..S3 high→low w/ price. These ARE on the chart.
      → If price gapped overnight and the Voodoo inputs still show the prior
        day's numbers, REMIND me to update R3..S3 before trading — stale levels
        = wrong targets.
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
   - Hard stop = **see `strategy/strategy.yaml.exits.hard_stop_pct` (currently
     −40%)** — file is source of truth; also exit on chart invalidation
     (signal flip, VWAP lost, MON EXIT, 3:30 close-out).
   - **Daily cap = 2 SPX trades. Two losses = done for the day.**
   - Conviction: **TREND** = full; **SCALP** = only if CONFLUENCE ≥3 and Flow
     not CONTRADICT; **EARLY** = prep only, never a live entry.
   - Time: entries only 9:45–2:30 ET, skip lunch 12–1, none after 2:30.
   - Verdict: **APPROVE** (all gates pass) / **APPROVE WITH CONCERNS** (mixed,
     smaller) / **REJECT** (Flow contradicts, confluence <3, EARLY-only, wrong
     time, or cap hit). Tag any [MEMORY] assumption.
   - If approved → TRADE PLAN: CALL/PUT · 0DTE strike · entry trigger · TP =
     next Voodoo (R1/R2 calls, S1/S2 puts) · stop per `strategy.yaml`
     (currently −40%) · "trade #_ of 2 today."

Subagent files live in `.claude/agents/` (quant-agent, flow-agent,
decision-agent). They load on-demand — they do not bloat every-session context.

**Auto-think at decisions (by design, not drift):** the decision prompts embed
reasoning triggers so Claude reasons hard at the money-moving moments WITHOUT you
typing them — `ultrathink` at the decision-agent verdict and the spx_0dte_desk
gates; `think hard` at the trade_desk gate report and the exit (HOLD/TP/CUT)
decisions. The data agents (quant, flow) and the morning brief stay fast by
design — do NOT add triggers there. One trigger per decision point is enough;
repeating it doesn't deepen reasoning further.

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
- **No blind retries.** If `place_option_order` returns an error, timeout, or
  empty response, do NOT retry. Call `get_option_orders` to check if it filled.
  If status is still unclear, halt and ask me to verify in the RH app.

Read-only dashboard trigger:
> "Read my Robinhood main account: portfolio health check — concentration risk,
> biggest losers, margin/cash balance, positions bleeding or near-worthless.
> Read-only, no trades. Tag [TOOL]."

Managing existing option positions (e.g. into expiry): pull the live mark +
P&L% vs what was paid, cross-check UW flow/GEX, then apply the **stop from
`strategy.yaml.exits.hard_stop_pct` (currently −40%)** — CUT if at/below the
stop, factor theta and distance to break-even.

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
7. Size = my call (confirm contracts); per-trade risk is capped by
   `strategy.yaml.exits.hard_stop_pct` (currently −40%), not a fixed $.

MANAGE & EXIT (every close also = review → approve → place):
8. **TP** = next Voodoo (R1/R2 calls, S1/S2 puts) → sell-to-close limit at target.
9. **Hard stop** = `strategy.yaml.exits.hard_stop_pct` (currently −40%) →
   sell-to-close immediately if hit.
10. **Chart invalidation** (signal flip, VWAP lost, MON EXIT) or **3:30 ET** → exit.
11. Log it as "trade #_ of 2 today." Two losses = done.

## Relay protocol (terminal = hands, strategist = brain, me = boss)

The terminal pulls data + previews/places orders. A separate strategist session
gives the GO/NO-GO. I (the user) relay between them and approve every real order.
There is no live link between sessions — I am the relay, by design.

Paste the strategist one of these:

ENTRY CHECK
- Quant: SIGNAL _ | CONFLUENCE _/6 | price _ | between Voodoo _ & _ | TIME _
- Flow: CONFIRM/CONTRADICT/MIXED | GEX regime _
- Decision verdict: _
- Order preview (review_option_order): SPX/SPY _ C/P strike _ | bid/ask _ |
  delta _ | cost _ | trade #_ of 2
→ reply: GO/NO-GO + strike/limit + the one deciding reason.

MANAGE CHECK
- Position: _ C/P _ | paid _ | now _ | P&L _%
- Chart: signal _ | VWAP _ | MON EXIT _ | time _
- Flow now: _
→ reply: HOLD / TAKE PROFIT / CUT (esp. the hard stop from `strategy.yaml` & Voodoo TP).

The strategist auto-applies: confluence ≥3, flow-confirm, ATM/~0.50 delta,
limit-at-mid, hard stop per `strategy.yaml.exits.hard_stop_pct`, Voodoo TP,
2-trade cap, 9:45–2:30 window. Fill the key
4 — signal, confluence, flow, order preview — and paste whatever the terminal
gives (raw is fine).

## What is NOT the problem (verified, don't chase it)

- **MCP servers are fine.** Their tools load **on-demand** (~4k tokens total),
  not all upfront. The long `tradingview-mcp` / `unusualwhales` tool lists in
  `/mcp` do **not** bloat context. Leave the MCP servers connected.
- Servers showing `needs authentication` (robinhood, gmail, calendar, drive)
  are harmless if unused — authenticate them only when you actually need them.

## Supervisor audit (second-model contradiction check)

`python3 run.py --supervise` sends the day-state (strategy, goal, positions,
journal, git log, freshness) to **MiniMax M3 (native API)** — a different
model on purpose, so it doesn't share this desk's blind spots. ADVISORY ONLY:
it prints CONTRADICTIONS / ROUTINE GAPS / SUGGESTIONS; its suggestions become
rules only via the Friday loop + user GO, never directly. It KEEPS MEMORY:
each memo is saved to `journal/audits/<date>.md` and the last 3 are fed back
into the next run, so it marks flags NEW / REPEAT xN and escalates what
festers. Needs
`MINIMAX_API_KEY` in `~/.zshrc` (env var, never in repo; falls back to
`OPENROUTER_API_KEY` if absent). ~1¢/run.
MANUAL trigger only — never schedule it (LaunchAgents post-mortem applies).
Charter prompt: `prompts/supervisor.md`. Code: `lib/supervisor.py`.

## Automation inventory — scheduled jobs (FIXED, do not re-enable)

Scheduled LaunchAgents (`spx.briefing` + `lotteryscanner`) were permanently
disabled 2026-06-16. They caused overnight token burns. Run the briefing
manually at the desk. Full post-mortem + kill/re-enable commands:
`scratch/post_mortem_launchagents.md`.

## Diagnostics

- `/context` — token breakdown by category (model, skills, messages, reads).
- `/mcp` — MCP server connection status.
- `/model` — view / change the active model.
- `claude --debug` — see MCP startup errors if a server won't connect.

## MCP config

- `.mcp.json` defines the project's `tradingview` MCP server. The `args` path
  must point to the real `tradingview-mcp-jackson/src/server.js` on **this**
  machine. If it's wrong, the server fails to start every session.
- `alpaca` (`@alpaca-open-api/mcp`) reads `ALPACA_API_KEY` +
  `ALPACA_API_SECRET` from the shell env (set them in `~/.zshrc`, never in
  this repo). `ALPACA_TOOLSETS=data` is set in `.mcp.json` ON PURPOSE — it
  strips every trading/order tool from the server. Do not add `trading` to
  that list; order flow goes through Robinhood MCP with manual approval only.
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
