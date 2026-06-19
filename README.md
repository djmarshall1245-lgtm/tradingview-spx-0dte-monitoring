# SPX / Equity-Options Self-Improving Desk

A terminal Claude Code trading system that **observes, decides, and learns** —
with **you as the GO** on every trade and every rule change. Combines patterns
from two builds onto your existing setup:

- **OBSERVE** (AI Pathways / "Options Monitor"): macro score, position Greeks,
  IV rank, per-name news, condition alerts. Reports facts, never trades.
- **DECIDE** (yours): quant/flow/decision subagents + A+ gates + relay protocol.
- **LEARN** (Hermes pattern): versioned strategy, trade journal, weekly
  one-variable reflection. The files learn; the model reads them fresh.

```
strategy/   goal.yaml · strategy.yaml · history/      ← the rules (LEARN)
journal/    trades.jsonl · hypotheses.jsonl           ← the memory (LEARN)
prompts/    morning_brief · trade_desk · friday_loop  ← the brains (paste-in)
lib/        greeks · macro_gate · snapshot · news ·    ← the data (OBSERVE)
            alerts · score · db · screenshot
data/       monitor.db · snapshots/ · shots/           ← local store (gitignored)
config.yaml · positions.yaml · run.py                  ← knobs + entrypoint
```

## What is the goal?
Maximize **expectancy per trade** = `(win% × avg_win$) − (loss% × avg_loss$)`,
without ever loosening a hard rail. See `strategy/goal.yaml`. (Win rate alone
is NOT the goal — with −40% stops it can lose money at 90% win rate.)

## One-time setup (on your Mac)
```bash
cd ~/path/to/tradingview-spx-0dte-monitoring
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py --score                  # sanity check (works with zero deps)
```
**No API keys needed.** Claude Code uses your existing subscription; the
per-name news enrichment runs through your Firecrawl + Unusual Whales MCPs
inside the morning-brief prompt — see `prompts/morning_brief.md`.
> The remote/web Claude session can't run the live data layer — it's a
> headless Linux container with no market access and no display. Live runs
> (`--brief`, `--snapshot`, `--shot`) happen here on your Mac.

## Daily use
```bash
python run.py --snapshot     # run EVERY trading day — builds IV-rank history
python run.py --brief        # pre-open monitor: macro + book + alerts + news
```
Then trade by pasting `prompts/trade_desk.md` into Claude Code and attaching
screenshots. You stay the GO.

## Screenshots — the "AI photos" pipeline
Capture chart/flow/gauge/chain straight off your screen so Claude reads them
without manual paste:
```bash
python run.py --shot --window     # click a window to grab it (easiest)
python run.py --shot chart        # grab a calibrated region from config.yaml
python lib/screenshot.py --all    # grab every named region at once
```
Files land in `data/shots/`; Claude Code can `Read` them.

**Calibrate screenshot regions (once):** take a full grab with
`python run.py --shot --full`, open it, note the pixel box of each pane, and
put `[x, y, width, height]` into `config.yaml → screenshots.regions`. Until
then, `--window` works with no calibration. (macOS `screencapture`; grant
Terminal **Screen Recording** permission in System Settings → Privacy.)

## Weekly learning loop (trigger C: every 5 closed trades OR every Friday)
Paste `prompts/friday_loop.md` into Claude Code. It scores the window by
expectancy, clusters by regime, evaluates last week's hypothesis, and proposes
**one** variable change — which it applies to `strategy.yaml` **only after your
GO** (gate #2), snapshotting the prior version to `strategy/history/`.

## Safety model
- **You are the GO twice:** every order, and every rule change.
- **Hard rails are constitutional** (`strategy.yaml → hard_rails_locked`): the
  loop may never widen stops, raise the drawdown cap, or remove the manual-GO
  step. Only you can, deliberately.
- **Monitor never routes orders.** It surfaces conditions like "hit your target
  level," never "buy/sell."
- **No 24/7 autonomy, no cloud daemon.** You run it when you sit down.
