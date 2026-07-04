# HERMATHENA BRAIN

A file-based, human-in-the-loop trading brain for the
`tradingview-spx-0dte-monitoring` repo. Built 2026-06-20 → 2026-06-21
in preparation for $1,000 equity-options go-live on Mon 2026-06-22.

## Why the name

In classical antiquity, a **Hermathena** was a double-herm sculpture
combining Hermes and Athena — a real ancient hybrid representing the
union of eloquence + execution (Hermes, god of commerce and messengers)
with strategic wisdom (Athena, goddess of disciplined craft). Cicero
famously owned one. Renaissance scholars used it as the ideal of the
integrated mind: the merchant who reasons, the strategist who acts.

That is exactly what this repo is:
- **The Hermes side** = the agent framework, MCPs, execution pipeline,
  messaging between Claude sessions and the broker.
- **The Athena side** = the strategy, the gates, the hard rails, the
  weekly reflection. The discipline that prevents the agent from doing
  anything it's not authorized to do.
- **The Brain** = the file-based memory that persists across sessions,
  so neither Hermes nor Athena starts from scratch each morning.

Naming aside: when you say "the brain", "the spine", "the system", or
"Hermathena" — they all refer to this same architecture.

## Architecture (the 4 layers + the gate)

```
                       YOU (the GO gate — twice)
                              │
   ┌──────────────────────────┼──────────────────────────┐
   ▼                          ▼                          ▼
OBSERVE                    DECIDE                      LEARN
(lib/ + data/)             (prompts/ + .claude/)       (strategy/ + journal/)
                              │
                              ▼
                       robinhood-trading MCP
                       (sub-account ••••3232)
```

| Layer | Folders | What it does |
|---|---|---|
| **OBSERVE** | `lib/`, `data/`, `run.py` | Deterministic Python: macro score, Greeks, IV rank, alerts, chain snapshots. Never trades. |
| **DECIDE** | `prompts/`, `.claude/agents/` | The 3 prompts (go, trade_desk, friday_loop) + 3 subagents (quant, flow, decision). Propose conditions; never auto-fire. |
| **LEARN** | `strategy/`, `journal/` | Versioned playbook + objective + history + trade log + hypothesis log. The Hermes-style spine. |
| **GATE** | (you) | Two manual approvals: GO on every trade, GO on every strategy bump. |

## Files that are load-bearing

| File | Role |
|---|---|
| `CLAUDE.md` | START-OF-SESSION rules (read YAML, /mcp check, date discipline) |
| `strategy/strategy.yaml` | Current playbook + `hard_rails_locked` (constitutional) |
| `strategy/goal.yaml` | Objective (expectancy per trade) + drawdown floor |
| `strategy/history/v{NNNN}.yaml` | Every prior strategy version |
| `journal/trades.jsonl` | Every closed trade, append-only |
| `journal/hypotheses.jsonl` | Weekly hypothesis log, one-variable rule |
| `config.yaml` | 12-name watchlist + sector map + macro weights |
| `prompts/go.md` | One-paste daily launcher |
| `prompts/morning_brief.md` | OBSERVE-layer brief (anti-fab + staleness + TOOL RECEIPT) |
| `prompts/trade_desk.md` | At-signal entry check (4 gates + anti-drift + TOOL RECEIPT) |
| `prompts/friday_loop.md` | Weekly reflection (one-variable rule, your GO) |
| `watchlists/leopold_holdings.yaml` | Q1 2026 13F context, smart-money-confirms flag |
| `prompts/leopold_run.md` | On-demand smart-money sweep of the Leopold book vs live tape |

## Daily routine (the whole brain in 3 actions)

1. Mac Terminal: `cd ~/tradingview-spx-0dte-monitoring && claude`
2. Claude Code: `Read prompts/go.md and run it.`
3. At a setup: paste `prompts/trade_desk.md` + screenshots → propose → **GO**.

Weekly (Friday close OR after 5 trades): paste `prompts/friday_loop.md`
→ reflect → strategy bump needs **GO**.

## Drift modes named and closed (so far)

The system gets sharper every time it drifts and we name the failure.
Current closed modes:

| Drift | Closed in | Trigger that caught it |
|---|---|---|
| Verbal recap overriding file | `CLAUDE.md` "FILE WINS" + each prompt's STEP 0 | $3-5 premium almost slipped back into recap when locked at $1-1.50 |
| Memory fabrication | morning_brief RULES 1-4 + mandatory ⑦ | MU at $1,100 with 17×$159 P/E math that didn't multiply |
| Stale-flow misuse | morning_brief ⑤ staleness discipline | Thursday UW tables dressed up as current Saturday data |
| Tool substitution | TOOL RECEIPT in morning_brief ⑧ + trade_desk step 6 | Web search used instead of Firecrawl |
| Date guessing | CLAUDE.md DATE & TIME DISCIPLINE | "Expires Monday (June 26)" — June 26 is Friday |
| Hardcoded number duplication | CLAUDE.md pointers to strategy.yaml | -50% in CLAUDE.md vs -40% in strategy.yaml |

Each one named because Claude failed it, then permanently closed.
That's the actual "self-improvement" — not the model getting smarter,
but the rules getting more specific every time the model drifts.

## What this is NOT

- Not the [Hermes agent software](https://github.com/NousResearch/hermes-agent)
  (different architecture; that's autonomous-by-default, this is
  human-gated-by-default)
- Not auto-running. Nothing fires on a cron. You trigger every action.
- Not a strategy. It's the disciplined harness that runs A strategy
  (whichever rules sit in `strategy.yaml` this week).
